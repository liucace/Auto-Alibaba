import importlib.util
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SKILL = (
    ROOT
    / "plugins"
    / "auto-alibaba"
    / "skills"
    / "upload-1688-products"
    / "SKILL.md"
)
SCRIPTS = (
    ROOT
    / "plugins"
    / "auto-alibaba"
    / "skills"
    / "upload-1688-products"
    / "scripts"
)


def _load(name: str):
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec = importlib.util.spec_from_file_location(f"test_{name}", SCRIPTS / f"{name}.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(SCRIPTS))


def test_upload_skill_child_environment_forces_utf8() -> None:
    module = _load("run_upload")

    environment = module.utf8_environment({"EXISTING": "1"})

    assert environment["EXISTING"] == "1"
    assert environment["PYTHONUTF8"] == "1"
    assert environment["PYTHONIOENCODING"] == "utf-8"


def test_upload_skill_square_check_rejects_non_square_image(tmp_path: Path) -> None:
    module = _load("preflight")
    square = tmp_path / "square.jpg"
    rectangle = tmp_path / "rectangle.jpg"
    Image.new("RGB", (100, 100)).save(square)
    Image.new("RGB", (100, 80)).save(rectangle)

    assert module.image_dimensions(square) == (100, 100)
    assert module.image_dimensions(rectangle) == (100, 80)


def test_skill_requires_agent_onboarding_before_upload() -> None:
    skill = SKILL.read_text(encoding="utf-8")

    command = (
        'powershell -NoProfile -ExecutionPolicy Bypass -File '
        '"<PROJECT_ROOT>\\agent-onboard.ps1" -Model "<MODEL>" -Open'
    )
    assert command in skill
    assert skill.index("agent-onboard.ps1") < skill.index("ensure_chrome.ps1")
    for status in (
        "NEEDS_SETUP",
        "NEEDS_MODEL",
        "NEEDS_PRICE_STOCK",
        "NEEDS_SOURCE_FILES",
        "READY_TO_UPLOAD",
        "NEEDS_LOGIN",
        "READY_TO_SAVE",
    ):
        assert status in skill
    assert "价格和库存不能为空" in skill
    assert "Codex Plugin 不是必需条件" in skill
    assert "init-product" not in skill
    assert "10000" not in skill
    assert "不得在同一轮" in skill


def test_skill_protects_all_user_business_inputs() -> None:
    skill = SKILL.read_text(encoding="utf-8")

    for phrase in (
        "不得删除、移动、改名、清空或覆盖",
        "price_inventory.xlsx",
        "data/",
        "automation/",
        "PDF",
        "照片",
        "明确授权",
    ):
        assert phrase in skill


def test_skill_documents_approved_geo_single_sku_and_fixed_tail_contract() -> None:
    skill = SKILL.read_text(encoding="utf-8")

    assert "外部输入仅限当前型号 PDF、至少四张真实产品照片，以及 Excel 中的价格和库存" in skill
    assert "标题不超过 60 个字符" in skill
    assert "ASCII 字符计 1、中文字符计 2" in skill
    assert "品牌、完整型号和产品名称" in skill
    assert "50/60Hz 斜杠参数" in skill
    assert "不得拆成多个 SKU" in skill
    assert "固定六张公司介绍图片" in skill
    assert "每个品牌" in skill
    assert "动态图片数量" in skill
    assert "当前品牌编号最大的相册" in skill
    assert "只允许创建下一编号并重试当前批次一次" in skill
    assert "永远不要点击“保存草稿”、发布或等价按钮" in skill
    assert "详情图为5张" not in skill
