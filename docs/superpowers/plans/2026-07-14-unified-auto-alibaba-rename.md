# Auto-Alibaba Unified Rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the public project, local root, and Plugin display identity to `Auto-Alibaba` while preserving the valid lowercase technical identifiers and all local business data.

**Architecture:** First make the repository content self-consistent and enforce the name with tests. Then refresh and validate the Plugin, push the tracked migration, rename the GitHub repository, update `origin`, and only then rename the local directory and refresh the Codex marketplace path.

**Tech Stack:** Git, GitHub CLI, PowerShell, Python 3.12, pytest, Ruff, mypy, Codex Plugin/Skill validators.

---

## File map

- Modify `tests/unit/test_distribution_contract.py`: enforce the public name, Plugin display name, clone URL, and absence of the standalone legacy name in Git-tracked text.
- Modify `README.md`: update repository URL, clone directory, and Plugin display text.
- Modify `AGENTS.md`: update repository guidance title.
- Modify `plugins/auto-alibaba/.codex-plugin/plugin.json`: change the display name and add the generated Codex cachebuster suffix.
- Modify `plugins/auto-alibaba/skills/upload-1688-products/SKILL.md`: update the project brand reference while preserving `auto-alibaba` and `AUTO_ALIBABA_ROOT`.
- Modify historical Markdown under `docs/superpowers/specs/` and `docs/superpowers/plans/`: migrate project names, GitHub URLs, and fixed project-directory examples.
- Keep `.agents/plugins/marketplace.json` source path as `./plugins/auto-alibaba`; the technical Plugin ID and outer folder already match the required lowercase format.
- Update external state after tracked changes pass: GitHub repository name, Git remote URL, local root directory, configured repository Marketplace path, and installed Skill copy.

### Task 1: Add the rename contract and migrate tracked text

**Files:**
- Modify: `tests/unit/test_distribution_contract.py`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `plugins/auto-alibaba/.codex-plugin/plugin.json`
- Modify: `plugins/auto-alibaba/skills/upload-1688-products/SKILL.md`
- Modify: tracked `*.md` files under `docs/superpowers/specs/` and `docs/superpowers/plans/`

- [ ] **Step 1: Write failing public-name contract tests**

Extend `tests/unit/test_distribution_contract.py` with imports and helpers that scan only Git-tracked text. Construct the forbidden pattern without embedding the standalone legacy name in the test itself:

```python
import re
import subprocess

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
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```powershell
python -m pytest tests/unit/test_distribution_contract.py -q
```

Expected: failures list tracked files containing the standalone legacy name and report the old Plugin display name/clone URL.

- [ ] **Step 3: Perform the bounded mechanical text migration**

Use Git's tracked file list and a case-sensitive negative-lookahead replacement so the correct new name is never changed a second time:

```powershell
$OldName = "Auto-" + "Alibab"
$NewName = "Auto-Alibaba"
$TextExtensions = @(".md", ".json", ".yaml", ".yml", ".py", ".ps1", ".toml")
$Pattern = [regex]::Escape($OldName) + "(?!a)"
$Tracked = git ls-files

foreach ($Relative in $Tracked) {
    $Path = Join-Path (Get-Location) $Relative
    if ($TextExtensions -notcontains [IO.Path]::GetExtension($Path).ToLowerInvariant()) {
        continue
    }
    $Content = [IO.File]::ReadAllText($Path, [Text.UTF8Encoding]::new($false))
    $Updated = [regex]::Replace($Content, $Pattern, $NewName)
    if ($Updated -ne $Content) {
        [IO.File]::WriteAllText($Path, $Updated, [Text.UTF8Encoding]::new($false))
    }
}
```

Then use `apply_patch` for the display-only spelling that has no hyphen:

```diff
-    "displayName": "Auto Alibaba",
+    "displayName": "Auto-Alibaba",
```

Do not rename `plugins/auto-alibaba`, the manifest ID `auto-alibaba`, `upload-1688-products`, or `AUTO_ALIBABA_ROOT`.

- [ ] **Step 4: Review the migration diff for accidental double suffixes**

Run:

```powershell
rg -n "Auto-Alibabaa|auto-alibabaa|AUTO_ALIBABAA" .
git diff -- README.md AGENTS.md plugins docs tests
```

Expected: no double-suffix match; every changed occurrence is a project brand, repository URL, or project-root example.

- [ ] **Step 5: Run the contract tests and verify GREEN**

```powershell
python -m pytest tests/unit/test_distribution_contract.py -q
```

Expected: all distribution-contract tests pass.

- [ ] **Step 6: Commit the tracked name migration**

```powershell
git add README.md AGENTS.md plugins/auto-alibaba/.codex-plugin/plugin.json plugins/auto-alibaba/skills/upload-1688-products/SKILL.md docs tests/unit/test_distribution_contract.py
git diff --cached --check
git commit -m "refactor: rename project to Auto-Alibaba"
```

### Task 2: Refresh and validate the existing Plugin

**Files:**
- Modify: `plugins/auto-alibaba/.codex-plugin/plugin.json`
- Modify: `tests/unit/test_distribution_contract.py`

- [ ] **Step 1: Add a failing cachebuster contract**

Add to the Plugin contract test:

```python
def test_plugin_version_has_one_codex_cachebuster() -> None:
    manifest = json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text("utf-8"))

    assert re.fullmatch(r"0\.1\.0\+codex\.local-\d{8}-\d{6}", manifest["version"])
```

- [ ] **Step 2: Run the cachebuster test and verify RED**

```powershell
python -m pytest tests/unit/test_distribution_contract.py::test_plugin_version_has_one_codex_cachebuster -q
```

Expected: FAIL because the current version is still `0.1.0` or has a prior cachebuster.

- [ ] **Step 3: Run the Plugin cachebuster helper**

```powershell
$PluginCreator = Join-Path $env:USERPROFILE ".codex\skills\.system\plugin-creator"
python (Join-Path $PluginCreator "scripts\update_plugin_cachebuster.py") ".\plugins\auto-alibaba"
```

Expected: the base version remains `0.1.0` and exactly one `+codex.local-YYYYMMDD-HHMMSS` suffix is present.

- [ ] **Step 4: Validate the Plugin, Skill, and focused tests**

```powershell
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$PluginCreator = Join-Path $env:USERPROFILE ".codex\skills\.system\plugin-creator"
$SkillCreator = Join-Path $env:USERPROFILE ".codex\skills\.system\skill-creator"
python (Join-Path $PluginCreator "scripts\validate_plugin.py") ".\plugins\auto-alibaba"
python (Join-Path $SkillCreator "scripts\quick_validate.py") ".\plugins\auto-alibaba\skills\upload-1688-products"
python -m pytest tests/unit/test_distribution_contract.py -q
```

Expected: both validators and all focused tests exit `0`.

- [ ] **Step 5: Commit the cachebuster contract and manifest update**

```powershell
git add plugins/auto-alibaba/.codex-plugin/plugin.json tests/unit/test_distribution_contract.py
git diff --cached --check
git commit -m "chore: refresh Auto-Alibaba plugin"
```

### Task 3: Verify and publish the tracked migration

**Files:**
- Verify all tracked files; no additional feature files are expected.

- [ ] **Step 1: Run the complete repository verification**

```powershell
python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m ruff check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m mypy app
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1 -CheckOnly
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
```

Expected: all tests pass; Ruff, mypy, and portable setup checks exit `0`.

- [ ] **Step 2: Verify the public-payload and name boundary**

```powershell
$Tracked = git ls-files
$ForbiddenFiles = $Tracked | Where-Object {
    $_ -match '(^|/)(price_inventory\.xlsx|data/draft_saved/|automation/|\.chrome-profile/)' -or
    $_ -match '\.(pdf|xlsx|xls|jpg|jpeg|png|webp)$'
}
if ($ForbiddenFiles) { $ForbiddenFiles; throw "Tracked business payload found" }

$Legacy = "Auto-" + "Alibab"
$LegacyHits = git grep -n -I -P "$([regex]::Escape($Legacy))(?!a)" -- .
if ($LegacyHits) { $LegacyHits; throw "Standalone legacy project name remains" }

git diff --check HEAD
git status --short
```

Expected: no tracked business payload, no standalone legacy project name, no whitespace errors, and only the user's known unrelated untracked files remain.

- [ ] **Step 3: Push the current `main` before external rename**

```powershell
git branch --show-current
git push origin main
```

Expected: branch is `main` and the tracked migration is published successfully.

### Task 4: Rename the GitHub repository and update `origin`

**External state:**
- Rename the repository under account `liucace`.
- Update local remote `origin`.

- [ ] **Step 1: Verify GitHub CLI auth and target availability**

```powershell
$Gh = "C:\Program Files\GitHub CLI\gh.exe"
& $Gh auth status
& $Gh repo view "liucace/Auto-Alibaba" --json nameWithOwner 2>$null
if ($LASTEXITCODE -eq 0) { throw "Target GitHub repository already exists" }
```

Expected: authenticated as `liucace`; the target repository name is not already occupied.

- [ ] **Step 2: Rename the GitHub repository**

Construct the old name to avoid reintroducing it into tracked documentation:

```powershell
$Gh = "C:\Program Files\GitHub CLI\gh.exe"
$OldRepository = "liucace/" + ("Auto-" + "Alibab")
& $Gh repo rename -R $OldRepository "Auto-Alibaba" --yes
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
```

- [ ] **Step 3: Update and verify the local remote**

```powershell
git remote set-url origin "https://github.com/liucace/Auto-Alibaba.git"
git fetch origin main
$Local = git rev-parse HEAD
$Remote = (git ls-remote origin refs/heads/main).Split("`t")[0]
if ($Local -ne $Remote) { throw "Remote main does not match local main" }
```

- [ ] **Step 4: Verify GitHub repository metadata**

```powershell
$Gh = "C:\Program Files\GitHub CLI\gh.exe"
$Metadata = & $Gh repo view "liucace/Auto-Alibaba" --json nameWithOwner,url,visibility,defaultBranchRef | ConvertFrom-Json
if ($Metadata.nameWithOwner -ne "liucace/Auto-Alibaba") { throw "GitHub rename mismatch" }
if ($Metadata.visibility -ne "PUBLIC") { throw "Visibility changed unexpectedly" }
if ($Metadata.defaultBranchRef.name -ne "main") { throw "Default branch changed unexpectedly" }
```

### Task 5: Rename the local root and refresh Codex discovery

**External/local state:**
- Rename the current `D:\` project root whose name lacks the final letter to `D:\Auto-Alibaba`.
- Refresh the repository Marketplace at the new absolute path.
- Sync the bundled Skill into the current user's installed Skill directory.

- [ ] **Step 1: Check local rename preconditions**

Run from `D:\`, not from inside the project:

```powershell
$OldRoot = Join-Path "D:\" ("Auto-" + "Alibab")
$NewRoot = "D:\Auto-Alibaba"
$ResolvedOld = (Resolve-Path -LiteralPath $OldRoot).Path
if ($ResolvedOld -ne $OldRoot) { throw "Unexpected source root: $ResolvedOld" }
if (Test-Path -LiteralPath $NewRoot) { throw "Target directory already exists: $NewRoot" }

$Profile = Join-Path $OldRoot ".chrome-profile"
$UsingProfile = Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" |
    Where-Object { $_.CommandLine -and $_.CommandLine.Contains($Profile) }
if ($UsingProfile) { throw "Close the dedicated Auto-Alibaba Chrome before renaming the project" }
```

If the dedicated Chrome is using the profile, stop and ask the user to close it. Do not terminate the process.

- [ ] **Step 2: Rename the local directory with one PowerShell move**

From `D:\`:

```powershell
$OldRoot = Join-Path "D:\" ("Auto-" + "Alibab")
$NewRoot = "D:\Auto-Alibaba"
Move-Item -LiteralPath $OldRoot -Destination $NewRoot
if (Test-Path -LiteralPath $OldRoot) { throw "Old project root still exists" }
if (-not (Test-Path -LiteralPath $NewRoot -PathType Container)) { throw "New root missing" }
```

All following commands use `D:\Auto-Alibaba` as the working directory.

- [ ] **Step 3: Verify the repository from its new root**

```powershell
git rev-parse --show-toplevel
git remote get-url origin
python -m pytest -q
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1 -CheckOnly
```

Expected: top level is `D:/Auto-Alibaba`, origin uses the new GitHub URL, tests pass, and setup checks pass.

- [ ] **Step 4: Sync the verified bundled Skill**

Copy only Git-tracked Skill files and compare SHA-256 hashes:

```powershell
$Root = (Resolve-Path ".").Path
$SourcePrefix = "plugins/auto-alibaba/skills/upload-1688-products/"
$Destination = Join-Path $env:USERPROFILE ".codex\skills\upload-1688-products"
$Tracked = git ls-files "$SourcePrefix*"

foreach ($RepoPath in $Tracked) {
    $Relative = $RepoPath.Substring($SourcePrefix.Length).Replace('/', '\')
    $Source = Join-Path $Root $RepoPath.Replace('/', '\')
    $Target = Join-Path $Destination $Relative
    New-Item -ItemType Directory -Force -Path (Split-Path $Target) | Out-Null
    Copy-Item -LiteralPath $Source -Destination $Target -Force
    if ((Get-FileHash $Source).Hash -ne (Get-FileHash $Target).Hash) {
        throw "Skill sync mismatch: $Relative"
    }
}
```

- [ ] **Step 5: Refresh the non-default repository Marketplace**

```powershell
$Codex = (Get-Command codex.exe -ErrorAction Stop).Source
& $Codex plugin marketplace add "D:\Auto-Alibaba"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Codex plugin add "auto-alibaba@personal"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
```

If the Codex app shell returns an access-denied error for `codex.exe`, do not edit Codex's global marketplace configuration by hand. Verify the repository marketplace file and provide the Codex View/Share deeplinks for the new absolute path so the user can reopen/reinstall the Plugin in the app.

- [ ] **Step 6: Run final verification at the new path**

```powershell
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$PluginValidator = Join-Path $env:USERPROFILE ".codex\skills\.system\plugin-creator\scripts\validate_plugin.py"
$SkillValidator = Join-Path $env:USERPROFILE ".codex\skills\.system\skill-creator\scripts\quick_validate.py"
python $PluginValidator ".\plugins\auto-alibaba"
python $SkillValidator ".\plugins\auto-alibaba\skills\upload-1688-products"
python $SkillValidator (Join-Path $env:USERPROFILE ".codex\skills\upload-1688-products")

$Local = git rev-parse HEAD
$Remote = (git ls-remote origin refs/heads/main).Split("`t")[0]
if ($Local -ne $Remote) { throw "Final local/remote mismatch" }
git status --short
```

Expected: all validators pass, local and remote `main` match, the old root is absent, and only the user's pre-existing unrelated untracked files remain.
