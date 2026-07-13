from __future__ import annotations

import argparse
import asyncio
import ctypes
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from collections.abc import Callable
from importlib import import_module
from pathlib import Path
from typing import Any, cast

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

session_api = import_module("inspect_session")
preflight_api = import_module("preflight")


CDP_URL = "http://127.0.0.1:9223"
RETRYABLE_MESSAGES = (
    "four hosted main image URLs did not reach the form model",
    "one hosted detail image URL did not reach TinyMCE",
    "one detail image did not finish uploading",
    "Target page, context or browser has been closed",
    "Browser has been closed",
    "Connection closed",
)


class ActiveUploadLock(RuntimeError):
    pass


def fingerprint(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"exists": False, "size": 0, "mtime_ns": 0, "sha256": ""}
    content = path.read_bytes()
    stat = path.stat()
    return {
        "exists": True,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def _canonical(value: object) -> str:
    return str(value or "").strip().upper()


def validate_run_state(path: Path, before: dict[str, Any], model: str) -> dict[str, Any]:
    after = fingerprint(path)
    if after == before:
        return {
            "ok": False,
            "status": "FAILED",
            "model": model,
            "checks": {"fresh_state": False},
            "message": "task_state.json was not updated by this run",
        }
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return {
            "ok": False,
            "status": "FAILED",
            "model": model,
            "checks": {"fresh_state": True, "valid_json": False},
            "message": f"{type(error).__name__}: {error}",
        }
    if _canonical(state.get("model")) != _canonical(model) or not session_api.is_current_state(
        state
    ):
        return {
            "ok": False,
            "status": "FAILED",
            "model": model,
            "checks": {"fresh_state": True, "current_schema": False},
            "message": "fresh task state has the wrong model or an unsupported schema",
        }
    status = str(state["status"])
    quality = state.get("quality_check", {})
    result = {
        "ok": status == "READY_TO_SAVE",
        "status": status,
        "model": _canonical(state["model"]),
        "checks": {
            "fresh_state": True,
            "current_schema": True,
            "quality_errors": quality.get("errors") if isinstance(quality, dict) else None,
        },
        "message": (
            "Upload completed and stopped before save."
            if status == "READY_TO_SAVE"
            else str(state.get("error") or f"Upload ended with {status}.")
        ),
        "state": state,
    }
    return result


def is_process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        process_query_limited_information = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(
            process_query_limited_information,
            False,
            pid,
        )
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def acquire_lock(
    path: Path,
    model: str,
    *,
    process_alive: Callable[[int], bool] = is_process_alive,
) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(2):
        token = uuid.uuid4().hex
        payload = {
            "pid": os.getpid(),
            "model": model,
            "started_at": time.time(),
            "token": token,
        }
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
                pid = int(existing.get("pid", 0))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                raise ActiveUploadLock(
                    f"upload lock exists and cannot be verified: {path}"
                ) from None
            if process_alive(pid):
                raise ActiveUploadLock(
                    f"another upload is active: model={existing.get('model')} pid={pid}"
                ) from None
            path.unlink(missing_ok=True)
            continue
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False)
        return {"path": path, "token": token}
    raise ActiveUploadLock(f"could not acquire upload lock: {path}")


def release_lock(handle: dict[str, Any]) -> None:
    path = Path(handle["path"])
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return
    if existing.get("token") == handle.get("token"):
        path.unlink(missing_ok=True)


def build_command(root: Path, model: str, cdp_url: str) -> list[str]:
    return [
        sys.executable,
        "-m",
        "app.cli",
        "run",
        model,
        "--root",
        str(root.resolve()),
        "--cdp-url",
        cdp_url,
    ]


def is_retryable(message: str) -> bool:
    return any(allowed in message for allowed in RETRYABLE_MESSAGES)


def run_cli(root: Path, model: str, cdp_url: str, *, timeout_seconds: int = 900) -> dict[str, Any]:
    process = subprocess.Popen(
        build_command(root, model, cdp_url),
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=utf8_environment(),
        shell=False,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
        return {
            "returncode": process.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        return {
            "returncode": -1,
            "stdout": stdout,
            "stderr": stderr,
            "timed_out": True,
        }


def utf8_environment(base: dict[str, str] | None = None) -> dict[str, str]:
    environment = dict(os.environ if base is None else base)
    environment["PYTHONUTF8"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    return environment


def run_prepare(root: Path, model: str, *, timeout_seconds: int = 300) -> dict[str, Any]:
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.cli",
            "prepare",
            model,
            "--root",
            str(root.resolve()),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=utf8_environment(),
        shell=False,
        timeout=timeout_seconds,
        check=False,
    )
    return {
        "returncode": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
    }


def prepared_artifacts_complete(root: Path, folder_key: str) -> bool:
    artifacts = root / "automation" / folder_key
    return all(
        (artifacts / name).is_file()
        for name in ("1688_payload.json", "image_analysis.json", "detail_assets.json")
    )


def _model_paths_from_project(root: Path, model: str) -> tuple[str, str]:
    resolved = str(root.resolve())
    if resolved not in sys.path:
        sys.path.insert(0, resolved)
    from app.ingest.model_number import model_folder_key, normalize_model

    normalized = normalize_model(model)
    return normalized, model_folder_key(normalized)


def _failure(model: str, message: str, **checks: Any) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "BLOCKED",
        "model": model,
        "checks": checks,
        "message": message,
    }


def execute(root: Path, model: str, cdp_url: str = CDP_URL) -> dict[str, Any]:
    root = root.resolve()
    if cdp_url != CDP_URL:
        return _failure(model, "Only local Google Chrome CDP 9223 is allowed.", cdp_url=False)
    try:
        normalized, folder_key = _model_paths_from_project(root, model)
    except Exception as error:
        return _failure(model, f"{type(error).__name__}: {error}", project_import=False)
    try:
        lock = acquire_lock(root / ".uploader.lock", normalized)
    except ActiveUploadLock as error:
        return _failure(normalized, str(error), upload_lock=False)

    try:
        if not prepared_artifacts_complete(root, folder_key):
            prepared = run_prepare(root, normalized)
            if prepared["stdout"]:
                print(str(prepared["stdout"]).rstrip(), file=sys.stderr)
            if prepared["stderr"]:
                print(str(prepared["stderr"]).rstrip(), file=sys.stderr)
            if prepared["returncode"] != 0:
                return _failure(
                    normalized,
                    str(prepared["stdout"] or prepared["stderr"] or "Preparation failed.").strip(),
                    prepare=False,
                )
        for attempt in range(2):
            try:
                session = asyncio.run(session_api.inspect_session(root, cdp_url, normalized))
            except Exception as error:
                return _failure(normalized, f"{type(error).__name__}: {error}", session=False)
            if session["status"] == "NEEDS_LOGIN":
                return _failure(
                    normalized,
                    "1688 login is required in the dedicated Chrome profile.",
                    login=False,
                )
            reuse_main_images = session["checks"].get("reusable_main_images") == 4
            local = preflight_api.check_product(
                root,
                normalized,
                reuse_main_images=reuse_main_images,
            )
            if not local["ok"]:
                return cast(dict[str, Any], local)

            state_path = root / "automation" / folder_key / "task_state.json"
            before = fingerprint(state_path)
            completed = run_cli(root, normalized, cdp_url)
            if completed["stdout"]:
                print(completed["stdout"].rstrip(), file=sys.stderr)
            if completed["stderr"]:
                print(completed["stderr"].rstrip(), file=sys.stderr)
            if completed["timed_out"]:
                return _failure(
                    normalized, "Uploader exceeded the 15-minute timeout.", timeout=False
                )

            state_result = validate_run_state(state_path, before, normalized)
            if completed["returncode"] == 0:
                return state_result

            diagnostic = "\n".join(
                [
                    str(completed["stdout"]),
                    str(completed["stderr"]),
                    str(state_result.get("message", "")),
                ]
            )
            if attempt == 0 and is_retryable(diagnostic):
                print("Retrying one allowlisted transient upload failure.", file=sys.stderr)
                continue
            return (
                state_result
                if state_result["checks"].get("fresh_state")
                else _failure(
                    normalized,
                    diagnostic.strip() or "Uploader failed without a fresh task state.",
                    cli_returncode=completed["returncode"],
                )
            )
        return _failure(normalized, "Uploader retry limit reached.", retry_limit=False)
    finally:
        release_lock(lock)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--cdp-url", default=CDP_URL)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = execute(args.root, args.model, args.cdp_url)
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
