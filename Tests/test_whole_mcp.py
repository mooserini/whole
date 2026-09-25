import json
import sqlite3
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from whole_store import Store
from whole_mcp import WholeMCPHandler, create_http_server, PROTOCOL_VERSION, SERVER_NAME, SERVER_VERSION


class WholeMCPHandlerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "whole.db"
        self.trail = Path(self.tmp.name) / "trail.jsonl"
        self.store = Store(self.db)
        
        # Seed test data with recent timestamps
        now = datetime.now(timezone.utc)
        ts1 = (now - timedelta(minutes=90)).isoformat()
        ts2 = (now - timedelta(minutes=60)).isoformat()
        ts3 = (now - timedelta(minutes=30)).isoformat()
        events = [
            {"ts": ts1, "source": "frontmost", "app": "com.apple.Terminal", "title": "Building whole project"},
            {"ts": ts2, "source": "frontmost", "app": "com.operasoftware.Opera", "title": "getadongle.com overview"},
            {"ts": ts3, "source": "frontmost", "app": "com.nousresearch.hermes", "title": "Hermes HUD"},
        ]
        for e in events:
            self.store.ingest(e)
        self.store.rebuild_segments()
        
        self.handler = WholeMCPHandler(self.db, self.trail)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_tool_definitions_schema(self):
        tools = self.handler.get_tool_definitions()
        tool_names = [t["name"] for t in tools]
        self.assertIn("whole_status", tool_names)
        self.assertIn("whole_health", tool_names)
        self.assertIn("whole_search", tool_names)
        self.assertIn("whole_timeline", tool_names)
        self.assertIn("whole_recent_events", tool_names)
        self.assertIn("whole_standup", tool_names)

    def test_whole_status_tool(self):
        content, is_error = self.handler.call_tool("whole_status", {})
        self.assertFalse(is_error)
        self.assertEqual(len(content), 1)
        data = json.loads(content[0]["text"])
        self.assertEqual(data["events"], 3)
        self.assertEqual(data["integrity"], "ok")

    def test_whole_health_tool(self):
        expected = {"overall": "healthy", "read_only": True, "repair_attempted": False}
        self.handler.health_checker = lambda: expected
        content, is_error = self.handler.call_tool("whole_health", {})
        self.assertFalse(is_error)
        self.assertEqual(json.loads(content[0]["text"]), expected)

    def test_whole_health_does_not_create_missing_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "missing" / "whole.db"
            trail = Path(tmp) / "trail.jsonl"
            handler = WholeMCPHandler(db, trail, health_checker=lambda: {
                "overall": "offline",
                "read_only": True,
                "repair_attempted": False,
            })
            content, is_error = handler.call_tool("whole_health", {})
            self.assertFalse(is_error)
            self.assertFalse(db.exists())
            self.assertEqual(json.loads(content[0]["text"])["overall"], "offline")

    def test_whole_search_tool(self):
        content, is_error = self.handler.call_tool("whole_search", {"query": "getadongle"})
        self.assertFalse(is_error)
        data = json.loads(content[0]["text"])
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["matches"][0]["title"], "getadongle.com overview")

        # Test search with no query
        err_content, err_is_error = self.handler.call_tool("whole_search", {})
        self.assertTrue(err_is_error)

    def test_whole_timeline_tool(self):
        content, is_error = self.handler.call_tool("whole_timeline", {"limit": 10})
        self.assertFalse(is_error)
        data = json.loads(content[0]["text"])
        self.assertGreaterEqual(data["count"], 1)
        self.assertIn("segments", data)

    def test_whole_recent_events_tool(self):
        content, is_error = self.handler.call_tool("whole_recent_events", {"limit": 2})
        self.assertFalse(is_error)
        data = json.loads(content[0]["text"])
        self.assertEqual(data["count"], 2)
        self.assertEqual(len(data["events"]), 2)

    def test_whole_standup_fallback_when_no_trail(self):
        content, is_error = self.handler.call_tool("whole_standup", {})
        self.assertTrue(is_error)

    def test_whole_standup_fallback_with_trail(self):
        # Create trail file
        self.trail.write_text(json.dumps({"ts": "2026-08-21T10:00:00-04:00", "source": "frontmost", "app": "com.apple.Terminal", "title": "Building"}) + "\n")
        # Keyless apple path: default is openrouter (needs a key), so opt in explicitly.
        content, is_error = self.handler.call_tool("whole_standup", {"provider": "apple"})
        self.assertFalse(is_error)
        data = json.loads(content[0]["text"])
        self.assertTrue("clerk" in data or "standup" in data)

    def test_json_rpc_initialize_and_ping(self):
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"},
        }
        resp = self.handler.handle_rpc(init_req)
        self.assertEqual(resp["id"], 1)
        self.assertEqual(resp["result"]["protocolVersion"], PROTOCOL_VERSION)
        self.assertEqual(resp["result"]["serverInfo"]["name"], SERVER_NAME)

        ping_req = {"jsonrpc": "2.0", "id": 2, "method": "ping"}
        ping_resp = self.handler.handle_rpc(ping_req)
        self.assertEqual(ping_resp["id"], 2)
        self.assertEqual(ping_resp["result"], {})

    def test_json_rpc_tools_list_and_call(self):
        list_req = {"jsonrpc": "2.0", "id": 10, "method": "tools/list"}
        list_resp = self.handler.handle_rpc(list_req)
        self.assertEqual(list_resp["id"], 10)
        tools = list_resp["result"]["tools"]
        self.assertGreaterEqual(len(tools), 5)

        call_req = {
            "jsonrpc": "2.0",
            "id": 11,
            "method": "tools/call",
            "params": {
                "name": "whole_search",
                "arguments": {"query": "Terminal"},
            },
        }
        call_resp = self.handler.handle_rpc(call_req)
        self.assertEqual(call_resp["id"], 11)
        self.assertFalse(call_resp["result"]["isError"])
        content_text = call_resp["result"]["content"][0]["text"]
        self.assertIn("Building whole project", content_text)

    def test_json_rpc_unknown_method(self):
        bad_req = {"jsonrpc": "2.0", "id": 99, "method": "non_existent_method"}
        bad_resp = self.handler.handle_rpc(bad_req)
        self.assertEqual(bad_resp["id"], 99)
        self.assertEqual(bad_resp["error"]["code"], -32601)


class WholeMCPHTTPServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "whole.db"
        self.trail = Path(self.tmp.name) / "trail.jsonl"
        self.store = Store(self.db)
        self.store.ingest({
            "ts": "2026-08-21T10:00:00-04:00",
            "source": "frontmost",
            "app": "com.apple.Terminal",
            "title": "HTTP server test",
        })
        self.handler = WholeMCPHandler(self.db, self.trail)
        
        # Pick free port
        self.server = create_http_server(self.handler, "127.0.0.1", 0)
        self.port = self.server.server_address[1]
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.store.close()
        self.tmp.cleanup()

    def test_http_health_endpoint(self):
        self.handler.health_checker = lambda: {
            "overall": "healthy",
            "read_only": True,
            "repair_attempted": False,
        }
        url = f"http://127.0.0.1:{self.port}/health"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data["status"], "ok")
            self.assertEqual(data["server"], SERVER_NAME)
            self.assertEqual(data["overall"], "healthy")

    def test_http_rpc_endpoint(self):
        url = f"http://127.0.0.1:{self.port}/rpc"
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "whole_status", "arguments": {}},
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            body = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(body["id"], 1)
            self.assertFalse(body["result"]["isError"])
            content = json.loads(body["result"]["content"][0]["text"])
            self.assertEqual(content["events"], 1)


    def test_http_dashboard_root_html(self):
        url = f"http://127.0.0.1:{self.port}/"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            self.assertEqual(resp.headers.get("Content-Type"), "text/html; charset=utf-8")
            body = resp.read().decode("utf-8")
            self.assertIn("<!DOCTYPE html>", body)
            self.assertIn("WHOLE", body)

    def test_http_api_status(self):
        url = f"http://127.0.0.1:{self.port}/api/status"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data["events"], 1)
            self.assertEqual(data["server"], SERVER_NAME)

    def test_http_api_timeline_and_recent(self):
        url = f"http://127.0.0.1:{self.port}/api/timeline"
        with urllib.request.urlopen(urllib.request.Request(url)) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertIn("segments", data)

        url_recent = f"http://127.0.0.1:{self.port}/api/recent?limit=5"
        with urllib.request.urlopen(urllib.request.Request(url_recent)) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data["count"], 1)

    def test_http_api_search(self):
        url = f"http://127.0.0.1:{self.port}/api/search?q=Terminal"
        with urllib.request.urlopen(urllib.request.Request(url)) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data["count"], 1)

    def test_http_api_standup(self):
        self.trail.write_text(json.dumps({"ts": "2026-08-21T10:00:00-04:00", "source": "frontmost", "app": "com.apple.Terminal", "title": "Building"}) + "\n")
        url = f"http://127.0.0.1:{self.port}/api/standup"
        req = urllib.request.Request(url, data=b'{"provider": "apple"}', headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue("clerk" in data or "standup" in data)


if __name__ == "__main__":
    unittest.main()
