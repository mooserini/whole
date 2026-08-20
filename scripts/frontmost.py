#!/usr/bin/env python3
"""Whole frontmost collector.

Polls the focused app + window title. Appends a JSONL event only when
the pair changes. No screenshots, no OCR, no clipboard.

Needs Accessibility (System Events), not Screen Recording.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_STORE = Path.home() / ".hermes" / "whole"
SKIP_APPS = {
    "com.apple.loginwindow",
    "com.apple.ScreenSaver.Engine",
    "com.apple.WindowServer",
    "loginwindow",
    "ScreenSaverEngine",
}
HERMES_TITLE_DENY = ("approval", "allow access", "wants to", "permission")


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def load_deny(path: Path) -> tuple[set[str], list[str]]:
    bundles: set[str] = set()
    titles: list[str] = []
    if not path.exists():
        return bundles, titles
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.lower().startswith("title:"):
            titles.append(line.split(":", 1)[1].strip().lower())
        else:
            bundles.add(line)
    return bundles, titles


def osascript(source: str, timeout: float = 4.0) -> str | None:
    try:
        proc = subprocess.run(
            ["/usr/bin/osascript", "-e", source],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.rstrip("\n")


def frontmost() -> dict[str, str] | None:
    script = """
    tell application "System Events"
      tell (first application process whose frontmost is true)
        set bid to ""
        try
          set bid to bundle identifier
        end try
        set nm to name
        set wn to ""
        try
          set wn to name of front window
        end try
        return bid & tab & nm & tab & wn
      end tell
    end tell
    """
    out = osascript(script)
    if out is None:
        return None
    parts = out.split("\t", 2)
    while len(parts) < 3:
        parts.append("")
    bundle, name, title = (p.strip() for p in parts)
    return {"bundle": bundle, "name": name, "title": title}


def denied(sample: dict[str, str], bundles: set[str], titles: list[str]) -> bool:
    bundle = (sample.get("bundle") or "").lower()
    name = (sample.get("name") or "").lower()
    title = (sample.get("title") or "").lower()
    if bundle in {b.lower() for b in bundles}:
        return True
    if name in {b.lower() for b in bundles}:
        return True
    if "hermes" in bundle or "hermes" in name:
        if any(tok in title for tok in HERMES_TITLE_DENY):
            return True
    if any(tok and tok in title for tok in titles):
        return True
    return True if bundle in {s.lower() for s in SKIP_APPS} or name in SKIP_APPS else False


def event_from(sample: dict[str, str]) -> dict:
    app = sample.get("bundle") or sample.get("name") or None
    title = sample.get("title") or None
    return {
        "ts": now_iso(),
        "source": "frontmost",
        "app": app,
        "title": title,
        "detail": None,
        "session_id": None,
        "path": None,
    }


def append_jsonl(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def key_of(sample: dict[str, str]) -> tuple[str, str]:
    return (sample.get("bundle") or sample.get("name") or "", sample.get("title") or "")


def log(msg: str) -> None:
    sys.stderr.write(f"{now_iso()} {msg}\n")
    sys.stderr.flush()


def run_once(store: Path) -> int:
    deny_bundles, deny_titles = load_deny(store / "deny.txt")
    sample = frontmost()
    if sample is None:
        log("frontmost: System Events failed (Accessibility off, or timeout)")
        return 2
    if denied(sample, deny_bundles, deny_titles):
        log(f"denied {sample.get('bundle') or sample.get('name')}")
        return 0
    ev = event_from(sample)
    append_jsonl(store / "trail.jsonl", ev)
    print(json.dumps(ev, ensure_ascii=False))
    return 0


def run_loop(store: Path, interval: float) -> int:
    trail = store / "trail.jsonl"
    last: tuple[str, str] | None = None
    misses = 0
    log(f"frontmost collector store={store} interval={interval}s (no screen, no OCR)")
    while True:
        deny_bundles, deny_titles = load_deny(store / "deny.txt")
        sample = frontmost()
        if sample is None:
            misses += 1
            if misses in (1, 6, 30):
                log("System Events failed — grant Accessibility to /usr/bin/osascript or this python")
            time.sleep(interval)
            continue
        misses = 0
        if denied(sample, deny_bundles, deny_titles):
            last = None
            time.sleep(interval)
            continue
        k = key_of(sample)
        if k != last:
            append_jsonl(trail, event_from(sample))
            last = k
        time.sleep(interval)


def main() -> int:
    parser = argparse.ArgumentParser(description="Whole frontmost collector")
    parser.add_argument("--store", default=str(DEFAULT_STORE))
    parser.add_argument("--interval", type=float, default=8.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    store = Path(os.path.expanduser(args.store))
    if args.once:
        return run_once(store)
    return run_loop(store, max(2.0, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
