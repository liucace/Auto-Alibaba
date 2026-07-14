from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

CDP_URL = "http://127.0.0.1:9223"
SESSION_PREFIX = "1688-uploader:"
OFFER_HOST = "offer-new.1688.com"


def _canonical(value: object) -> str:
    return str(value or "").strip().upper()


def _is_offer_url(url: object) -> bool:
    parsed = urlparse(str(url or ""))
    return (
        parsed.scheme == "https"
        and parsed.hostname == OFFER_HOST
        and "/industry/publish.htm" in parsed.path
    )


def is_current_state(state: object) -> bool:
    if not isinstance(state, dict) or not _canonical(state.get("model")):
        return False
    status = state.get("status")
    browser = state.get("browser")
    if status == "FAILED":
        return (
            isinstance(state.get("error"), str)
            and bool(state["error"].strip())
            and isinstance(browser, dict)
            and browser.get("cdp_url") == CDP_URL
            and _is_offer_url(browser.get("page_url"))
        )
    if status not in {"READY_TO_SAVE", "BLOCKED"}:
        return False
    quality = state.get("quality_check")
    detail = state.get("detail")
    if (
        not isinstance(quality, dict)
        or not isinstance(detail, dict)
        or not isinstance(browser, dict)
    ):
        return False
    raw_errors = quality.get("errors")
    if not isinstance(raw_errors, (int, str)):
        return False
    try:
        errors = int(raw_errors)
    except ValueError:
        return False
    expected_errors = errors == 0 if status == "READY_TO_SAVE" else errors > 0
    image_count = detail.get("image_count")
    image_sources = detail.get("image_sources")
    valid_images = (
        isinstance(image_count, int)
        and isinstance(image_sources, list)
        and all(isinstance(item, str) and bool(item.strip()) for item in image_sources)
        and image_count == len(image_sources)
        and image_count == len(set(image_sources))
        and image_count >= 5
    )
    return (
        expected_errors
        and detail.get("template_version") == "geo-evidence-v3"
        and valid_images
        and browser.get("cdp_url") == CDP_URL
        and _is_offer_url(browser.get("page_url"))
    )


def read_state_candidates(root: Path) -> list[dict[str, Any]]:
    candidates: list[tuple[int, dict[str, Any]]] = []
    for path in (root / "automation").glob("*/task_state.json"):
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if is_current_state(loaded):
            candidates.append((path.stat().st_mtime_ns, loaded))
    candidates.sort(key=lambda item: item[0], reverse=True)
    return [state for _, state in candidates]


def resolve_model(page_models: list[str], state_models: list[str]) -> str | None:
    pages = {_canonical(model) for model in page_models if _canonical(model)}
    states = {_canonical(model) for model in state_models if _canonical(model)}
    common = pages & states
    return next(iter(common)) if len(common) == 1 else None


def is_reusable_page(
    *,
    requested_model: str,
    window_name: str,
    url: str,
    form_model: str,
    main_image_urls: list[str],
) -> bool:
    wanted = _canonical(requested_model)
    urls = list(dict.fromkeys(main_image_urls))
    return (
        _canonical(window_name) == _canonical(f"{SESSION_PREFIX}{wanted}")
        and _is_offer_url(url)
        and _canonical(form_model) == wanted
        and len(urls) == 4
        and all(urlparse(item).hostname == "cbu01.alicdn.com" for item in urls)
    )


def _load_project_helpers(
    root: Path,
) -> tuple[Callable[[str], str], Callable[[list[str]], list[str]]]:
    resolved = str(root.resolve())
    if resolved not in sys.path:
        sys.path.insert(0, resolved)
    from app.ingest.model_number import normalize_model
    from app.publisher.playwright_port import normalize_main_image_urls

    return normalize_model, normalize_main_image_urls


async def inspect_session(
    root: Path,
    cdp_url: str = CDP_URL,
    requested_model: str | None = None,
) -> dict[str, Any]:
    if cdp_url != CDP_URL:
        raise ValueError("only local Google Chrome CDP 9223 is allowed")
    normalize_model, normalize_urls = _load_project_helpers(root)
    wanted = normalize_model(requested_model) if requested_model else None

    from playwright.async_api import async_playwright

    runtime = await async_playwright().start()
    pages_result: list[dict[str, Any]] = []
    authentication = "unknown"
    try:
        browser = await runtime.chromium.connect_over_cdp(cdp_url)
        if not browser.contexts:
            raise RuntimeError("Chrome 9223 has no browser context")
        for context in browser.contexts:
            for page in context.pages:
                url = page.url
                parsed = urlparse(url)
                if parsed.scheme not in {"http", "https"}:
                    continue
                host = parsed.hostname or ""
                if "login" in host or "login" in parsed.path.lower():
                    authentication = "unauthenticated"
                elif host == "work.1688.com" and authentication != "unauthenticated":
                    authentication = "authenticated"
                try:
                    facts = await page.evaluate(
                        """() => {
                          const visible = element => !!(element.offsetWidth || element.offsetHeight || element.getClientRects().length);
                          const skuInputs = [...document.querySelectorAll('#guid-skuTable input')].filter(visible);
                          const values = skuInputs.map(input => (input.value || '').trim()).filter(Boolean);
                          const images = [...document.querySelectorAll('#guid-primaryPicture img')]
                            .map(image => image.src)
                            .filter(Boolean);
                          const title = document.querySelector('input[placeholder^="建议使用通俗的产品名称"]');
                          return {
                            windowName: window.name || '',
                            formModel: values.length ? values[values.length - 1] : '',
                            mainImages: images,
                            publishFormVisible: !!title && visible(title),
                          };
                        }"""
                    )
                except Exception:
                    continue
                if (
                    facts.get("publishFormVisible")
                    and _is_offer_url(url)
                    and authentication != "unauthenticated"
                ):
                    authentication = "authenticated"
                window_name = str(facts.get("windowName", ""))
                form_model = str(facts.get("formModel", ""))
                urls = normalize_urls([str(item) for item in facts.get("mainImages", [])])
                tagged_model = ""
                if window_name.startswith(SESSION_PREFIX):
                    tagged_model = normalize_model(window_name.removeprefix(SESSION_PREFIX))
                reusable = bool(
                    wanted
                    and is_reusable_page(
                        requested_model=wanted,
                        window_name=window_name,
                        url=url,
                        form_model=form_model,
                        main_image_urls=urls,
                    )
                )
                pages_result.append(
                    {
                        "url": url,
                        "window_name": window_name,
                        "tagged_model": tagged_model,
                        "form_model": normalize_model(form_model) if form_model else "",
                        "main_image_count": len(urls),
                        "reusable_main_images": reusable,
                    }
                )
    finally:
        await runtime.stop()

    states = read_state_candidates(root)
    page_models = [page["tagged_model"] for page in pages_result if page["tagged_model"]]
    state_models = [str(state["model"]) for state in states]
    resolved_model = wanted or resolve_model(page_models, state_models)
    reusable_count = max(
        (page["main_image_count"] for page in pages_result if page["reusable_main_images"]),
        default=0,
    )
    return {
        "ok": authentication != "unauthenticated",
        "status": "NEEDS_LOGIN" if authentication == "unauthenticated" else "READY",
        "model": resolved_model,
        "checks": {
            "cdp_connected": True,
            "authentication": authentication,
            "tagged_pages": len(page_models),
            "current_states": len(states),
            "reusable_main_images": reusable_count,
        },
        "message": "Chrome session inspected without navigation or form changes.",
        "pages": pages_result,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--cdp-url", default=CDP_URL)
    parser.add_argument("--model")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        result = asyncio.run(inspect_session(args.root.resolve(), args.cdp_url, args.model))
    except Exception as error:
        result = {
            "ok": False,
            "status": "BLOCKED",
            "model": args.model,
            "checks": {"cdp_connected": False},
            "message": f"{type(error).__name__}: {error}",
        }
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
