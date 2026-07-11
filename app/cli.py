import asyncio
import json
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer

from app.ingest.inventory import load_inventory
from app.ingest.model_number import normalize_model
from app.products.loader import load_prepared_product
from app.publisher.form_plan import build_form_plan
from app.publisher.orchestrator import ProductUploader, UploadResult
from app.publisher.playwright_port import Playwright1688Port, build_session_tag
from app.workflow.state_store import JsonStateStore

app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    """Persistent 1688 draft automation."""


@app.command()
def version() -> None:
    """Print the uploader version."""
    typer.echo("1688-draft-automation 0.1.0")


def doctor_checks(root: Path, cdp_url: str) -> list[tuple[str, bool, str]]:
    python_ok = sys.version_info >= (3, 12)
    workbook = root / "price_inventory.xlsx"
    cdp_ok = False
    cdp_detail = cdp_url
    if cdp_url.startswith("http://127.0.0.1:"):
        try:
            with urllib.request.urlopen(  # noqa: S310 - loopback URL is validated above
                f"{cdp_url.rstrip('/')}/json/version", timeout=2
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
                cdp_ok = bool(payload.get("webSocketDebuggerUrl"))
        except (OSError, ValueError, json.JSONDecodeError):
            cdp_ok = False
    return [
        ("Python 3.12+", python_ok, sys.version.split()[0]),
        ("price_inventory.xlsx", workbook.is_file(), str(workbook)),
        ("Chrome CDP 9223", cdp_ok, cdp_detail),
    ]


@app.command()
def doctor(
    root: Annotated[Path, typer.Option("--root", help="商品资料工作区")] = Path("."),
    cdp_url: Annotated[str, typer.Option("--cdp-url")] = "http://127.0.0.1:9223",
) -> None:
    """Run read-only environment checks."""
    checks = doctor_checks(root.resolve(), cdp_url)
    for name, ok, detail in checks:
        typer.echo(f"{name}: {'OK' if ok else 'FAIL'} ({detail})")
    if not all(ok for _, ok, _ in checks):
        raise typer.Exit(code=1)


@dataclass(frozen=True)
class CommandResult:
    model: str
    errors: int
    advice: tuple[str, ...]
    ready: bool


def build_task_state(*, result: UploadResult, cdp_url: str, page_url: str) -> dict[str, object]:
    return {
        "model": result.model,
        "status": "READY_TO_SAVE" if result.ready_to_save else "BLOCKED",
        "quality_check": {
            "errors": result.errors,
            "remaining_advice": list(result.advice),
        },
        "detail": {
            "template_version": "reference-faithful-v1",
            "local_html": str(result.detail_html_path),
            "drawing_url": result.detail_drawing_url,
            "image_count": result.detail_image_count,
        },
        "browser": {"cdp_url": cdp_url, "page_url": page_url},
    }


async def run_product(
    *, root: Path, model: str, cdp_url: str, albums: tuple[str, ...]
) -> CommandResult:
    normalized = normalize_model(model)
    inventory = load_inventory(root / "price_inventory.xlsx", normalized)
    product = load_prepared_product(root, normalized, price=inventory.price, stock=inventory.stock)
    plan = build_form_plan(product.payload)
    port = await Playwright1688Port.connect(
        cdp_url=cdp_url,
        category_url=plan.category_url,
        albums=albums,
        session_tag=build_session_tag(normalized),
    )
    store = JsonStateStore(product.artifacts_directory / "task_state.json")
    try:
        result = await ProductUploader(port).run(product)
        state = build_task_state(
            result=result,
            cdp_url=cdp_url,
            page_url=port.page.url,
        )
        store.save(state)
        return CommandResult(
            model=normalized,
            errors=result.errors,
            advice=result.advice,
            ready=result.ready_to_save,
        )
    except Exception as error:
        store.save(
            {
                "model": normalized,
                "status": "FAILED",
                "error": f"{type(error).__name__}: {error}",
                "browser": {"cdp_url": cdp_url, "page_url": port.page.url},
            }
        )
        raise
    finally:
        await port.disconnect()


@app.command()
def run(
    model: Annotated[str, typer.Argument(help="完整商品型号")],
    root: Annotated[Path, typer.Option("--root", help="商品资料工作区")] = Path("."),
    cdp_url: Annotated[str, typer.Option("--cdp-url")] = "http://127.0.0.1:9223",
    album: Annotated[list[str] | None, typer.Option("--album")] = None,
) -> None:
    """Fill one product and stop before saving the draft."""
    albums = tuple(album or ["ebm(L)", "ebm(LCC)"])
    result = asyncio.run(
        run_product(root=root.resolve(), model=model, cdp_url=cdp_url, albums=albums)
    )
    if result.ready:
        typer.echo(
            f"{result.model}: READY_TO_SAVE; errors=0; stopped before save; "
            f"advice={','.join(result.advice) or '-'}"
        )
        return
    typer.echo(f"{result.model}: BLOCKED; errors={result.errors}")
    raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
