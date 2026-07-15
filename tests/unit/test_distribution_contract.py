import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

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
    assert "agent-onboard.ps1" in readme
    assert "START-HERE.md" in readme
    assert "1688价格和库存" in readme
    assert "PDF规格书" in readme
    assert "四张" in readme
    assert "保存草稿" in agents
    for content in (setup, agents, readme):
        assert "D:\\Auto-Alibaba" not in content
        assert f"C:\\Users\\{ORIGINAL_USER}" not in content


def test_agent_onboard_is_model_free_and_forwards_only_explicit_model() -> None:
    script = (ROOT / "agent-onboard.ps1").read_text(encoding="utf-8")

    assert "[string]$Model" in script
    assert '"--model"' in script
    assert "app.cli" in script
    assert '"onboard"' in script
    assert "init-product" not in script
    assert "W3G800" not in script
    assert "W3G630" not in script
    assert "Remove-Item" not in script
    assert "Move-Item" not in script


@pytest.mark.skipif(shutil.which("powershell") is None, reason="Windows PowerShell required")
def test_agent_onboard_without_model_does_not_create_business_data(
    tmp_path: Path,
) -> None:
    clone = tmp_path / "clean-project"
    shutil.copytree(ROOT / "app", clone / "app")
    for name in ("agent-onboard.ps1", "pyproject.toml"):
        shutil.copy2(ROOT / name, clone / name)

    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(clone / "agent-onboard.ps1"),
        ],
        cwd=clone,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )

    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    assert completed.returncode == 0
    assert payload["status"] in {"NEEDS_SETUP", "NEEDS_MODEL"}
    assert not (clone / "price_inventory.xlsx").exists()
    assert not (clone / "data").exists()
    assert not (clone / "automation").exists()


def test_beginner_guidance_states_exact_user_inputs_and_locations() -> None:
    start = (ROOT / "START-HERE.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    for phrase in (
        "完整型号",
        "规格书 PDF",
        "至少四张",
        "价格",
        "库存",
        "price_inventory.xlsx",
        "data/draft_saved/<FOLDER_KEY>/",
    ):
        assert phrase in start
    assert "品牌、参数、标题、SKU、JSON 和详情页由智能体" in start
    assert "不要创建示例型号" in start
    assert "不要删除、移动或覆盖" in start
    assert "START-HERE.md" in readme
    assert "一次只" in agents
    assert "未经用户明确授权" in agents


def test_beginner_facing_guidance_has_no_fixed_business_model() -> None:
    for relative in ("START-HERE.md", "README.md", "AGENTS.md"):
        content = (ROOT / relative).read_text(encoding="utf-8")
        assert "W3G800-KS39-03/F01" not in content
        assert "W3G630-NU33-03" not in content


def test_double_click_entry_only_opens_project_and_instructions() -> None:
    script = (ROOT / "开始使用.ps1").read_text(encoding="utf-8")

    assert "$PSScriptRoot" in script
    assert "START-HERE.md" in script
    assert "Start-Process" in script
    for forbidden in (
        "app.cli",
        "setup.ps1",
        "agent-onboard.ps1",
        "run_upload",
        "chrome.exe",
        "Remove-Item",
        "Move-Item",
    ):
        assert forbidden not in script


def test_setup_never_initializes_a_product() -> None:
    setup = (ROOT / "setup.ps1").read_text(encoding="utf-8")

    assert "init-product" not in setup
    assert "app.cli onboard" not in setup
