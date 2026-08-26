#!/usr/bin/env python3
"""Read-only runtime health checks for Whole's macOS collector."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Sequence, Tuple

DEFAULT_LABEL = "com.moosenberg.whole-frontmost"
DEFAULT_PLIST = Path.home() / "Library/LaunchAgents" / f"{DEFAULT_LABEL}.plist"
DEFAULT_TRAIL = Path.home() / ".hermes/whole/trail.jsonl"
DEFAULT_STALE_AFTER = 120.0
ACCESSIBILITY_PROBE = (
    'tell application "System Events" to '
    "get name of first process whose frontmost is true"
)

CommandRunner = Callable[[Sequence[str]], Any]


def _default_runner(args: Sequence[str]) -> Any:
    return subprocess.run(
        list(args),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


def _run(runner: CommandRunner, args: Sequence[str]) -> Tuple[int, str, str]:
    try:
        result = runner(args)
    except OSError as exc:
        return 127, "", str(exc)
    return (
        int(getattr(result, "returncode", 1)),
        str(getattr(result, "stdout", "") or ""),
        str(getattr(result, "stderr", "") or ""),
    )


def _read_last_event(trail_path: Path) -> Tuple[Optional[str], Optional[str]]:
    try:
        lines = trail_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return None, str(exc)
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            return None, f"invalid JSONL: {exc}"
        timestamp = event.get("ts")
        if not isinstance(timestamp, str):
            return None, "last event has no string 'ts' field"
        return timestamp, None
    return None, "trail is empty"


def _parse_launchd(output: str) -> Dict[str, Any]:
    state_match = re.search(r"^\s*state\s*=\s*(.+)$", output, re.MULTILINE)
    active_match = re.search(r"^\s*active count\s*=\s*(\d+)$", output, re.MULTILINE)
    pid_match = re.search(r"^\s*pid\s*=\s*(\d+)$", output, re.MULTILINE)
    properties_match = re.search(r"^\s*properties\s*=\s*(.+)$", output, re.MULTILINE)
    state = state_match.group(1).strip() if state_match else None
    active_count = int(active_match.group(1)) if active_match else 0
    pid = int(pid_match.group(1)) if pid_match else None
    properties = properties_match.group(1).strip().split(" | ") if properties_match else []
    return {
        "state": state,
        "active_count": active_count,
        "pid": pid,
        "properties": properties,
        "running": state == "running" and active_count > 0 and pid is not None,
    }


def health_report(
    *,
    plist_path: Path = DEFAULT_PLIST,
    trail_path: Path = DEFAULT_TRAIL,
    label: str = DEFAULT_LABEL,
    uid: Optional[str] = None,
    now: Optional[datetime] = None,
    stale_after_seconds: float = DEFAULT_STALE_AFTER,
    runner: Optional[CommandRunner] = None,
) -> Dict[str, Any]:
    """Return a read-only health report for the collector runtime."""
    plist_path = Path(plist_path).expanduser()
    trail_path = Path(trail_path).expanduser()
    uid = str(os.getuid()) if uid is None else str(uid)
    runner = runner or _default_runner
    now = now or datetime.now(timezone.utc)
    launchd_target = f"gui/{uid}/{label}"

    plist_exists = plist_path.exists()
    plist_valid = False
    plist_error = None
    if plist_exists:
        code, stdout, stderr = _run(runner, ["plutil", "-lint", str(plist_path)])
        plist_valid = code == 0
        if not plist_valid:
            plist_error = stderr.strip() or stdout.strip() or f"plutil exited with {code}"

    launchd_code, launchd_stdout, launchd_stderr = _run(
        runner, ["launchctl", "print", launchd_target]
    )
    registered = launchd_code == 0
    launchd_info = _parse_launchd(launchd_stdout) if registered else {
        "state": None,
        "active_count": 0,
        "pid": None,
        "properties": [],
        "running": False,
    }
    if not registered:
        launchd_info["error"] = launchd_stderr.strip() or launchd_stdout.strip() or f"launchctl exited with {launchd_code}"

    disabled_code, disabled_stdout, disabled_stderr = _run(
        runner, ["launchctl", "print-disabled", f"gui/{uid}"]
    )
    enabled: Optional[bool] = None
    if disabled_code == 0:
        match = re.search(rf'"{re.escape(label)}"\s*=>\s*(enabled|disabled)', disabled_stdout)
        if match:
            enabled = match.group(1) == "enabled"

    pid = launchd_info.get("pid")
    process_code = None
    process_stdout = ""
    process_stderr = ""
    if pid is not None:
        process_code, process_stdout, process_stderr = _run(
            runner, ["ps", "-p", str(pid), "-o", "pid=,command="]
        )
    process_alive = bool(pid is not None and process_code == 0 and process_stdout.strip())
    process = {
        "alive": process_alive,
        "pid": pid,
        "command": process_stdout.strip() or None,
    }
    if pid is not None and not process_alive:
        process["error"] = process_stderr.strip() or "launchd reported a PID, but ps found no live process"

    last_observed_at, trail_error = (None, "trail does not exist")
    if trail_path.exists():
        last_observed_at, trail_error = _read_last_event(trail_path)
    age_seconds: Optional[float] = None
    if last_observed_at:
        try:
            observed = datetime.fromisoformat(last_observed_at)
            if observed.tzinfo is None:
                observed = observed.replace(tzinfo=timezone.utc)
            age_seconds = max(0.0, (now - observed).total_seconds())
        except ValueError as exc:
            trail_error = f"invalid timestamp: {exc}"
    trail_fresh = age_seconds is not None and age_seconds <= stale_after_seconds
    trail = {
        "exists": trail_path.exists(),
        "path": str(trail_path),
        "fresh": trail_fresh,
        "age_seconds": age_seconds,
        "stale_after_seconds": stale_after_seconds,
        "change_only_semantics": True,
    }
    if trail_error:
        trail["error"] = trail_error

    accessibility_code, accessibility_stdout, accessibility_stderr = _run(
        runner, ["osascript", "-e", ACCESSIBILITY_PROBE]
    )
    accessibility = {
        "usable": accessibility_code == 0,
        "frontmost_process": accessibility_stdout.strip() or None,
    }
    if accessibility_code != 0:
        accessibility["error"] = accessibility_stderr.strip() or accessibility_stdout.strip() or f"osascript exited with {accessibility_code}"

    hard_fail = (
        not plist_exists
        or not plist_valid
        or not registered
        or not launchd_info["running"]
        or not process_alive
        or not accessibility["usable"]
    )
    trail_missing_or_invalid = (
        not trail["exists"] or last_observed_at is None or trail_error is not None
    )
    if hard_fail:
        overall = "offline"
    elif trail_missing_or_invalid:
        overall = "degraded"
    else:
        overall = "healthy"

    return {
        "overall": overall,
        "read_only": True,
        "repair_attempted": False,
        "label": label,
        "uid": uid,
        "plist": {
            "path": str(plist_path),
            "exists": plist_exists,
            "valid": plist_valid,
            **({"error": plist_error} if plist_error else {}),
        },
        "launchd": {
            "target": launchd_target,
            "registered": registered,
            "enabled": enabled,
            **launchd_info,
        },
        "process": process,
        "trail": trail,
        "last_observed_at": last_observed_at,
        "accessibility": accessibility,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Whole collector health check")
    parser.add_argument("--plist", default=str(DEFAULT_PLIST))
    parser.add_argument("--trail", default=str(DEFAULT_TRAIL))
    parser.add_argument("--uid")
    parser.add_argument("--stale-after", type=float, default=DEFAULT_STALE_AFTER)
    args = parser.parse_args()
    result = health_report(
        plist_path=Path(args.plist),
        trail_path=Path(args.trail),
        uid=args.uid,
        stale_after_seconds=args.stale_after,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["overall"] == "healthy" else 1


if __name__ == "__main__":
    raise SystemExit(main())
