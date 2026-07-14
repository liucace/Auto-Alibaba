import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "plugins"
    / "auto-alibaba"
    / "skills"
    / "upload-1688-products"
    / "scripts"
    / "run_upload.py"
)


def _load_run_upload():
    scripts = SCRIPT.parent
    sys.path.insert(0, str(scripts))
    try:
        spec = importlib.util.spec_from_file_location("test_run_upload_module", SCRIPT)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(scripts))


def test_prepared_artifacts_are_stale_when_evidence_is_newer(tmp_path: Path) -> None:
    module = _load_run_upload()
    artifacts = tmp_path / "automation" / "DP201AT-2122HBL.GN"
    artifacts.mkdir(parents=True)
    evidence = artifacts / "preparation_evidence.json"
    evidence.write_text("{}", encoding="utf-8")
    for name in ("1688_payload.json", "image_analysis.json", "detail_assets.json"):
        path = artifacts / name
        path.write_text("{}", encoding="utf-8")
        path.touch()
    future = evidence.stat().st_mtime + 10
    os.utime(evidence, (future, future))

    assert module.prepared_artifacts_complete(tmp_path, "DP201AT-2122HBL.GN") is False


def test_execute_stops_on_input_guide_before_lock_or_prepare(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_run_upload()
    calls: list[str] = []
    guided = {
        "ok": False,
        "status": "NEEDS_INPUT",
        "model": "W3G800-KS39-03/F01",
        "folder_key": "W3G800-KS39-03F01",
        "created": [str(tmp_path / "price_inventory.xlsx")],
        "checks": {"pdf_files": 0, "source_images": 0},
        "requirements": [
            {
                "key": "source_files",
                "purpose": "保存PDF和照片。",
                "action": "放入PDF和四张照片。",
                "ready": False,
            }
        ],
        "message": "请补充资料。",
    }
    monkeypatch.setattr(
        module,
        "_product_inputs_from_project",
        lambda root, model: ("W3G800-KS39-03/F01", "W3G800-KS39-03F01", guided),
    )
    monkeypatch.setattr(module, "acquire_lock", lambda *args, **kwargs: calls.append("lock"))
    monkeypatch.setattr(module, "run_prepare", lambda *args, **kwargs: calls.append("prepare"))

    result = module.execute(tmp_path, "W3G800-KS39-03/F01")

    assert result == guided
    assert calls == []
    assert not (tmp_path / ".uploader.lock").exists()


def test_execute_ready_inputs_reach_lock_and_prepare_in_order(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_run_upload()
    events: list[str] = []

    def guide(root: Path, model: str):
        events.append("guide")
        return (
            "W3G800-KS39-03/F01",
            "W3G800-KS39-03F01",
            {"ok": True, "status": "READY", "checks": {"pdf_files": 1, "source_images": 4}},
        )

    def lock(path: Path, model: str):
        events.append("lock")
        return {"path": path, "token": "test"}

    def prepare(root: Path, model: str):
        events.append("prepare")
        return {"returncode": 2, "stdout": "preparation stopped", "stderr": ""}

    monkeypatch.setattr(module, "_product_inputs_from_project", guide)
    monkeypatch.setattr(module, "acquire_lock", lock)
    monkeypatch.setattr(module, "release_lock", lambda handle: events.append("release"))
    monkeypatch.setattr(module, "prepared_artifacts_complete", lambda root, key: False)
    monkeypatch.setattr(module, "run_prepare", prepare)

    result = module.execute(tmp_path, "W3G800-KS39-03/F01")

    assert result["checks"] == {"prepare": False}
    assert events == ["guide", "lock", "prepare", "release"]
