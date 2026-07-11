from pathlib import Path


def test_production_source_contains_no_publish_click() -> None:
    root = Path(__file__).resolve().parents[3] / "app" / "publisher"
    combined = "\n".join(path.read_text(encoding="utf-8") for path in root.rglob("*.py")).lower()

    assert "submitformbutton').click" not in combined
    assert 'submitformbutton").click' not in combined
    assert "我要发布').click" not in combined
