import importlib.util
import sys
from pathlib import Path

from PIL import Image

SCRIPTS = Path.home() / ".codex" / "skills" / "upload-1688-products" / "scripts"


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
