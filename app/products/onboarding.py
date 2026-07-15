from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.ingest.inventory import inspect_inventory_values, load_inventory
from app.products.input_onboarding import initialize_product_inputs


@dataclass(frozen=True)
class OnboardingResult:
    ok: bool
    status: str
    model: str | None
    folder_key: str | None
    created: tuple[str, ...]
    checks: dict[str, object]
    paths: dict[str, str]
    next_action: str
    message: str

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "status": self.status,
            "model": self.model,
            "folder_key": self.folder_key,
            "created": list(self.created),
            "checks": self.checks,
            "paths": self.paths,
            "next_action": self.next_action,
            "message": self.message,
        }


def _needs_model(root: Path) -> OnboardingResult:
    return OnboardingResult(
        ok=False,
        status="NEEDS_MODEL",
        model=None,
        folder_key=None,
        created=(),
        checks={"model_provided": False},
        paths={"project_root": str(root)},
        next_action="请告诉我准备上传商品的完整型号。",
        message="尚未提供真实型号；没有创建任何商品资料。",
    )


def onboard_product(root: Path, model: str | None) -> OnboardingResult:
    resolved_root = root.resolve()
    if model is None or not model.strip():
        return _needs_model(resolved_root)

    initialized = initialize_product_inputs(resolved_root, model)
    workbook = resolved_root / "price_inventory.xlsx"
    source = resolved_root / "data" / "draft_saved" / initialized.folder_key
    presence = inspect_inventory_values(workbook, initialized.model)
    checks = {
        **initialized.checks,
        "model_provided": True,
        "price_present": presence.price_present,
        "stock_present": presence.stock_present,
    }
    paths = {
        "project_root": str(resolved_root),
        "inventory_workbook": str(workbook.resolve()),
        "source_directory": str(source.resolve()),
    }

    if not presence.price_present or not presence.stock_present:
        missing = [
            name
            for name, present in (
                ("价格", presence.price_present),
                ("库存", presence.stock_present),
            )
            if not present
        ]
        next_action = (
            f"请在已打开的 Excel 中填写当前完整型号的{'和'.join(missing)}，"
            "填写后告诉我“已填好”。"
        )
        return OnboardingResult(
            ok=False,
            status="NEEDS_PRICE_STOCK",
            model=initialized.model,
            folder_key=initialized.folder_key,
            created=initialized.created,
            checks=checks,
            paths=paths,
            next_action=next_action,
            message=next_action,
        )

    load_inventory(workbook, initialized.model)
    pdf_value = initialized.checks["pdf_files"]
    image_value = initialized.checks["source_images"]
    if not isinstance(pdf_value, int) or not isinstance(image_value, int):
        raise TypeError("source file counts must be integers")
    if pdf_value < 1:
        next_action = (
            "请把至少一份包含当前完整型号的规格书 PDF，直接放入已打开的型号文件夹，"
            "完成后告诉我“已放好”。"
        )
        status = "NEEDS_SOURCE_FILES"
    elif image_value < 4:
        remaining = 4 - image_value
        next_action = (
            f"请再把{remaining}张当前型号的真实产品照片直接放入已打开的型号文件夹，"
            "完成后告诉我“已放好”。"
        )
        status = "NEEDS_SOURCE_FILES"
    else:
        next_action = "当前型号资料齐全；可以进入证据准备和1688上传流程。"
        status = "READY_TO_UPLOAD"

    return OnboardingResult(
        ok=status == "READY_TO_UPLOAD",
        status=status,
        model=initialized.model,
        folder_key=initialized.folder_key,
        created=initialized.created,
        checks=checks,
        paths=paths,
        next_action=next_action,
        message=next_action,
    )
