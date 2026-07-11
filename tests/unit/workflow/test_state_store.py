from pathlib import Path

from app.workflow.state_store import JsonStateStore


def test_state_write_is_atomic(tmp_path: Path) -> None:
    path = tmp_path / "task_state.json"
    store = JsonStateStore(path)

    store.save({"model": "W3G630-NU33-03", "status": "READY_TO_SAVE"})

    assert store.load() == {"model": "W3G630-NU33-03", "status": "READY_TO_SAVE"}
    assert not list(tmp_path.glob("*.tmp"))
