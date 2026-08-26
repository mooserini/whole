import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from whole_health import health_report


class FakeRunner:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def __call__(self, args):
        key = tuple(args)
        self.calls.append(key)
        return self.responses.get(
            key,
            SimpleNamespace(returncode=1, stdout="", stderr="not configured"),
        )


class WholeHealthTests(unittest.TestCase):
    def test_reports_healthy_registered_running_collector(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plist = root / "com.moosenberg.whole-frontmost.plist"
            trail = root / "trail.jsonl"
            plist.write_text("placeholder")
            trail.write_text(json.dumps({
                "ts": "2026-08-26T15:22:43-04:00",
                "source": "frontmost",
                "app": "com.nousresearch.hermes",
                "title": "Hermes",
            }) + "\n")
            uid = "501"
            label = "com.moosenberg.whole-frontmost"
            launchd = f"gui/{uid}/{label}"
            runner = FakeRunner({
                ("plutil", "-lint", str(plist)): SimpleNamespace(returncode=0, stdout="OK", stderr=""),
                ("launchctl", "print", launchd): SimpleNamespace(
                    returncode=0,
                    stdout=(
                        "state = running\n"
                        "active count = 1\n"
                        "pid = 26716\n"
                        "properties = keepalive | runatload\n"
                    ),
                    stderr="",
                ),
                ("launchctl", "print-disabled", f"gui/{uid}"): SimpleNamespace(
                    returncode=0,
                    stdout=f'\t"{label}" => enabled\n',
                    stderr="",
                ),
                ("ps", "-p", "26716", "-o", "pid=,command="): SimpleNamespace(
                    returncode=0,
                    stdout="26716 /Library/Developer/CommandLineTools/usr/bin/python3 scripts/frontmost.py\n",
                    stderr="",
                ),
                ("osascript", "-e", "tell application \"System Events\" to get name of first process whose frontmost is true"): SimpleNamespace(
                    returncode=0,
                    stdout="Hermes\n",
                    stderr="",
                ),
            })

            result = health_report(
                plist_path=plist,
                trail_path=trail,
                uid=uid,
                now=datetime.fromisoformat("2026-08-26T15:23:00-04:00"),
                runner=runner,
            )

            self.assertEqual(result["overall"], "healthy")
            self.assertTrue(result["read_only"])
            self.assertTrue(result["plist"]["exists"])
            self.assertTrue(result["plist"]["valid"])
            self.assertTrue(result["launchd"]["registered"])
            self.assertTrue(result["launchd"]["running"])
            self.assertTrue(result["launchd"]["enabled"])
            self.assertTrue(result["process"]["alive"])
            self.assertTrue(result["trail"]["fresh"])
            self.assertTrue(result["accessibility"]["usable"])
            self.assertEqual(result["last_observed_at"], "2026-08-26T15:22:43-04:00")
            self.assertEqual(result["repair_attempted"], False)

    def test_reports_offline_when_launchd_job_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plist = root / "missing.plist"
            trail = root / "trail.jsonl"
            trail.write_text(json.dumps({
                "ts": "2026-08-26T15:22:43+00:00",
                "source": "frontmost",
                "app": "com.nousresearch.hermes",
                "title": "Hermes",
            }) + "\n")
            uid = "501"
            label = "com.moosenberg.whole-frontmost"
            runner = FakeRunner({
                ("launchctl", "print", f"gui/{uid}/{label}"): SimpleNamespace(
                    returncode=113, stdout="", stderr="Could not find specified service"
                ),
                ("launchctl", "print-disabled", f"gui/{uid}"): SimpleNamespace(
                    returncode=0, stdout=f'\t"{label}" => enabled\n', stderr=""
                ),
                ("osascript", "-e", "tell application \"System Events\" to get name of first process whose frontmost is true"): SimpleNamespace(
                    returncode=0, stdout="Hermes\n", stderr=""
                ),
            })

            result = health_report(
                plist_path=plist,
                trail_path=trail,
                uid=uid,
                now=datetime.fromisoformat("2026-08-26T15:23:00+00:00"),
                runner=runner,
            )

            self.assertEqual(result["overall"], "offline")
            self.assertFalse(result["plist"]["exists"])
            self.assertFalse(result["launchd"]["registered"])
            self.assertFalse(result["process"]["alive"])
            self.assertTrue(result["launchd"]["enabled"])
            self.assertFalse(result["repair_attempted"])

    def test_keeps_live_collector_healthy_when_change_only_trail_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plist = root / "com.moosenberg.whole-frontmost.plist"
            trail = root / "trail.jsonl"
            plist.write_text("placeholder")
            trail.write_text(json.dumps({
                "ts": "2026-08-26T14:00:00+00:00",
                "source": "frontmost",
                "app": "com.nousresearch.hermes",
                "title": "Hermes",
            }) + "\n")
            uid = "501"
            label = "com.moosenberg.whole-frontmost"
            launchd = f"gui/{uid}/{label}"
            runner = FakeRunner({
                ("plutil", "-lint", str(plist)): SimpleNamespace(returncode=0, stdout="OK", stderr=""),
                ("launchctl", "print", launchd): SimpleNamespace(
                    returncode=0,
                    stdout="state = running\nactive count = 1\npid = 26716\nproperties = keepalive | runatload\n",
                    stderr="",
                ),
                ("launchctl", "print-disabled", f"gui/{uid}"): SimpleNamespace(
                    returncode=0, stdout=f'\t"{label}" => enabled\n', stderr=""
                ),
                ("ps", "-p", "26716", "-o", "pid=,command="): SimpleNamespace(
                    returncode=0, stdout="26716 /Library/Developer/CommandLineTools/usr/bin/python3 frontmost.py\n", stderr=""
                ),
                ("osascript", "-e", "tell application \"System Events\" to get name of first process whose frontmost is true"): SimpleNamespace(
                    returncode=0, stdout="Hermes\n", stderr=""
                ),
            })

            result = health_report(
                plist_path=plist,
                trail_path=trail,
                uid=uid,
                now=datetime.fromisoformat("2026-08-26T15:23:00+00:00"),
                stale_after_seconds=120,
                runner=runner,
            )

            self.assertEqual(result["overall"], "healthy")
            self.assertTrue(result["launchd"]["running"])
            self.assertTrue(result["process"]["alive"])
            self.assertFalse(result["trail"]["fresh"])
            self.assertTrue(result["trail"]["change_only_semantics"])


if __name__ == "__main__":
    unittest.main()
