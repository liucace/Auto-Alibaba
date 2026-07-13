import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "auto-alibaba"
SKILL = PLUGIN / "skills" / "upload-1688-products"
ORIGINAL_USER = "\u5c0f\u57ce"
TEXT_SUFFIXES = frozenset({".md", ".json", ".yaml", ".yml", ".py", ".ps1", ".toml"})
LEGACY_PROJECT_PATTERN = re.compile("Auto-" + r"Alibab(?!a)", flags=re.IGNORECASE)


def _tracked_text_files() -> list[Path]:
    completed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    relative_paths = completed.stdout.decode("utf-8").split("\0")
    return [
        ROOT / relative
        for relative in relative_paths
        if relative and Path(relative).suffix.lower() in TEXT_SUFFIXES
    ]


def test_repository_plugin_and_marketplace_are_wired_with_relative_paths() -> None:
    manifest = json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    marketplace = json.loads(
        (ROOT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8")
    )

    assert manifest["name"] == "auto-alibaba"
    assert manifest["skills"] == "./skills/"
    entry = next(item for item in marketplace["plugins"] if item["name"] == "auto-alibaba")
    assert entry["source"]["path"] == "./plugins/auto-alibaba"


def test_public_project_name_is_consistent_across_tracked_text() -> None:
    stale: list[str] = []
    for path in _tracked_text_files():
        content = path.read_text(encoding="utf-8")
        if LEGACY_PROJECT_PATTERN.search(content):
            stale.append(str(path.relative_to(ROOT)))

    assert stale == []


def test_public_repository_and_plugin_display_use_auto_alibaba() -> None:
    manifest = json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text("utf-8"))
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    assert manifest["name"] == "auto-alibaba"
    assert manifest["interface"]["displayName"] == "Auto-Alibaba"
    assert "https://github.com/liucace/Auto-Alibaba.git" in readme
    assert "Set-Location Auto-Alibaba" in readme
    assert agents.startswith("# Auto-Alibaba Repository Guidance")


def test_plugin_version_has_one_codex_cachebuster() -> None:
    manifest = json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text("utf-8"))

    assert re.fullmatch(r"0\.1\.0\+codex\.\d{14}", manifest["version"])


def test_distributable_plugin_has_no_original_machine_paths() -> None:
    files = [path for path in PLUGIN.rglob("*") if path.is_file()]

    assert files
    for path in files:
        if path.suffix.lower() in {".md", ".py", ".ps1", ".yaml", ".json"}:
            content = path.read_text(encoding="utf-8")
            assert "D:\\Auto-Alibaba" not in content
            assert f"C:\\Users\\{ORIGINAL_USER}" not in content


def test_tracked_documentation_has_no_original_user_profile() -> None:
    for path in (ROOT / "docs").rglob("*.md"):
        content = path.read_text(encoding="utf-8")
        assert f"C:/Users/{ORIGINAL_USER}" not in content
        assert f"C:\\Users\\{ORIGINAL_USER}" not in content


def test_business_data_and_credentials_remain_ignored() -> None:
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")

    for pattern in (
        ".chrome-profile/",
        "data/draft_saved/",
        "automation/*/",
        "price_inventory.xlsx",
        ".env",
    ):
        assert pattern in ignored


def test_setup_and_guidance_are_portable() -> None:
    setup = (ROOT / "setup.ps1").read_text(encoding="utf-8")
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "[switch]$CheckOnly" in setup
    assert "$PSScriptRoot" in setup
    assert "python -m app.cli doctor" in readme
    assert "python -m app.cli init-product" in readme
    assert "1688价格和库存" in readme
    assert "PDF规格书" in readme
    assert "四张" in readme
    assert "保存草稿" in agents
    for content in (setup, agents, readme):
        assert "D:\\Auto-Alibaba" not in content
        assert f"C:\\Users\\{ORIGINAL_USER}" not in content
