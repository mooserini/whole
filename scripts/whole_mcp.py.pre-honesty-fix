#!/usr/bin/env python3
"""Model Context Protocol (MCP) server & Local Web Dashboard for Whole workstream memory.

Supports:
1. stdio transport (local agent integration: Hermes, Claude Code, Cursor, Codex)
2. HTTP/SSE transport (tailnet cross-box agent integration, non-colliding port)
3. Zero-dependency Web GUI served at http://localhost:39400/
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, unquote, urlparse

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from whole_store import Store
from whole_health import health_report

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "whole-mcp"
SERVER_VERSION = "1.0.0"

DEFAULT_DB_PATH = Path.home() / ".hermes/whole/whole.db"
DEFAULT_TRAIL_PATH = Path.home() / ".hermes/whole/trail.jsonl"
DEFAULT_PORT = 39400
DEFAULT_HOST = "127.0.0.1"


_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Whole &mdash; Open Workstream Memory</title>
  <style>
    :root {
      --bg: #121314;
      --surface: #1a1b1d;
      --surface-elevated: #222427;
      --border: #2f3236;
      --border-light: #3d4147;
      --text: #f0ede6;
      --text-muted: #8e949e;
      --copper: #c48b5e;
      --copper-hover: #d99f70;
      --gold: #d7c5b2;
      --green: #34c759;
      --red: #ff453a;
      --blue: #0a84ff;
      --purple: #bf5af2;
      --font-mono: "Menlo", "SF Mono", "Courier New", monospace;
      --font-sans: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", Roboto, sans-serif;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: var(--font-sans);
      font-size: 14px;
      line-height: 1.5;
      padding: 0;
      overflow-x: hidden;
    }
    header {
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 14px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      position: sticky;
      top: 0;
      z-index: 100;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .logo {
      font-family: var(--font-mono);
      font-weight: 700;
      font-size: 16px;
      letter-spacing: 1.5px;
      color: var(--gold);
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .pulse-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--green);
      box-shadow: 0 0 8px rgba(52, 199, 89, 0.6);
      animation: pulse 2s infinite ease-in-out;
    }
    @keyframes pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.4; transform: scale(0.85); }
    }
    .status-tag {
      font-family: var(--font-mono);
      font-size: 11px;
      text-transform: uppercase;
      padding: 2px 8px;
      border-radius: 4px;
      background: rgba(52, 199, 89, 0.15);
      color: var(--green);
      border: 1px solid rgba(52, 199, 89, 0.3);
    }
    .header-actions {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .search-input {
      background: var(--bg);
      border: 1px solid var(--border);
      color: var(--text);
      font-family: var(--font-mono);
      font-size: 13px;
      padding: 6px 14px;
      border-radius: 6px;
      width: 280px;
      outline: none;
      transition: border-color 0.2s;
    }
    .search-input:focus {
      border-color: var(--copper);
    }
    button {
      background: var(--surface-elevated);
      color: var(--text);
      border: 1px solid var(--border-light);
      padding: 6px 14px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 500;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 6px;
      transition: all 0.15s ease;
    }
    button:hover {
      background: var(--border);
      border-color: var(--copper);
    }
    button.primary {
      background: var(--copper);
      color: #121314;
      font-weight: 600;
      border-color: var(--copper-hover);
    }
    button.primary:hover {
      background: var(--copper-hover);
    }
    main {
      padding: 20px 24px;
      max-width: 1400px;
      margin: 0 auto;
      display: flex;
      flex-direction: column;
      gap: 20px;
    }
    .vitals-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 14px;
    }
    .card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
    }
    .vital-title {
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      color: var(--text-muted);
      margin-bottom: 6px;
      font-family: var(--font-mono);
    }
    .vital-value {
      font-size: 24px;
      font-weight: 700;
      color: var(--text);
      font-family: var(--font-mono);
    }
    .vital-sub {
      font-size: 12px;
      color: var(--text-muted);
      margin-top: 4px;
    }
    .ribbon-container {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
    }
    .ribbon-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
    }
    .section-title {
      font-size: 13px;
      font-weight: 600;
      color: var(--gold);
      text-transform: uppercase;
      letter-spacing: 1px;
      font-family: var(--font-mono);
    }
    .ribbon-bar {
      height: 24px;
      background: var(--bg);
      border-radius: 4px;
      display: flex;
      overflow: hidden;
      border: 1px solid var(--border);
    }
    .ribbon-segment {
      height: 100%;
      transition: opacity 0.15s;
      position: relative;
    }
    .ribbon-segment:hover {
      opacity: 0.8;
      cursor: pointer;
    }
    .ribbon-legend {
      display: flex;
      flex-wrap: wrap;
      gap: 14px;
      margin-top: 12px;
      font-size: 12px;
      color: var(--text-muted);
    }
    .legend-item {
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .legend-color {
      width: 10px;
      height: 10px;
      border-radius: 2px;
    }
    .content-grid {
      display: grid;
      grid-template-columns: 1.2fr 0.8fr;
      gap: 20px;
    }
    @media (max-width: 960px) {
      .content-grid { grid-template-columns: 1fr; }
    }
    .events-panel, .clerk-panel {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .panel-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 8px;
      border-bottom: 1px solid var(--border);
    }
    .events-list {
      display: flex;
      flex-direction: column;
      gap: 8px;
      max-height: 580px;
      overflow-y: auto;
      padding-right: 4px;
    }
    .events-list::-webkit-scrollbar {
      width: 6px;
    }
    .events-list::-webkit-scrollbar-thumb {
      background: var(--border-light);
      border-radius: 3px;
    }
    .event-row {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 10px 14px;
      display: flex;
      flex-direction: column;
      gap: 4px;
      transition: border-color 0.15s;
    }
    .event-row:hover {
      border-color: var(--border-light);
    }
    .event-meta {
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 11px;
      color: var(--text-muted);
      font-family: var(--font-mono);
    }
    .app-badge {
      font-size: 11px;
      padding: 1px 6px;
      border-radius: 3px;
      background: var(--surface-elevated);
      color: var(--gold);
      border: 1px solid var(--border-light);
      font-family: var(--font-mono);
    }
    .event-title {
      font-size: 13px;
      color: var(--text);
      word-break: break-word;
    }
    .redaction-badge {
      display: inline-block;
      font-family: var(--font-mono);
      font-size: 11px;
      font-weight: 600;
      color: var(--red);
      background: rgba(255, 69, 58, 0.15);
      border: 1px solid rgba(255, 69, 58, 0.3);
      padding: 1px 5px;
      border-radius: 3px;
      margin: 0 2px;
    }
    .standup-box {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 18px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }
    .headline-box {
      font-size: 15px;
      font-weight: 600;
      color: var(--gold);
      line-height: 1.4;
      padding-bottom: 12px;
      border-bottom: 1px solid var(--border);
    }
    .standup-section-title {
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      color: var(--text-muted);
      font-family: var(--font-mono);
      margin-bottom: 8px;
    }
    .standup-list {
      list-style-type: none;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .standup-list li {
      position: relative;
      padding-left: 18px;
      font-size: 13px;
      color: var(--text);
    }
    .standup-list li::before {
      content: "•";
      position: absolute;
      left: 4px;
      color: var(--copper);
      font-weight: bold;
    }
    .search-results-box {
      display: none;
      background: var(--surface);
      border: 1px solid var(--copper);
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 20px;
    }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <div class="logo">
        <div class="pulse-dot"></div>
        WHOLE
      </div>
      <span class="status-tag">Live Trail</span>
    </div>
    <div class="header-actions">
      <input type="text" id="searchInput" class="search-input" placeholder="Search memory (FTS5)..." onkeyup="handleSearch(event)">
      <button onclick="loadAllData()"><span>⟳</span> Refresh</button>
      <button class="primary" onclick="triggerStandup()" id="clerkBtn"><span>⚡</span> Run AFM Clerk</button>
    </div>
  </header>

  <main>
    <div id="searchBox" class="search-results-box">
      <div class="panel-header">
        <span class="section-title">Search Results</span>
        <button onclick="closeSearch()">Close</button>
      </div>
      <div id="searchResultsList" class="events-list" style="margin-top: 10px; max-height: 300px;"></div>
    </div>

    <div class="vitals-grid">
      <div class="card">
        <div class="vital-title">Total Observations</div>
        <div class="vital-value" id="valEvents">&mdash;</div>
        <div class="vital-sub" id="valEventsSub">Recorded on disk</div>
      </div>
      <div class="card">
        <div class="vital-title">Active Time (Lower Bound)</div>
        <div class="vital-value" id="valActiveTime">&mdash;</div>
        <div class="vital-sub">Excludes idle/gaps</div>
      </div>
      <div class="card">
        <div class="vital-title">Privacy Boundary</div>
        <div class="vital-value" style="color: var(--green);" id="valRedactions">&mdash;</div>
        <div class="vital-sub">Zero sensitive fields leaked</div>
      </div>
      <div class="card">
        <div class="vital-title">Collector Daemon</div>
        <div class="vital-value" style="color: var(--green);">RUNNING</div>
        <div class="vital-sub">com.moosenberg.whole-frontmost</div>
      </div>
    </div>

    <div class="ribbon-container">
      <div class="ribbon-header">
        <span class="section-title">Workstream Focus Ribbon (Active App Distribution)</span>
        <span class="vital-sub" id="ribbonMeta">&mdash;</span>
      </div>
      <div class="ribbon-bar" id="ribbonBar"></div>
      <div class="ribbon-legend" id="ribbonLegend"></div>
    </div>

    <div class="content-grid">
      <div class="events-panel">
        <div class="panel-header">
          <span class="section-title">Live Observation Stream</span>
          <span class="vital-sub" id="streamMeta">Latest activity</span>
        </div>
        <div class="events-list" id="eventsList">
          <div style="padding: 20px; text-align: center; color: var(--text-muted);">Loading live stream...</div>
        </div>
      </div>

      <div class="clerk-panel">
        <div class="panel-header">
          <span class="section-title">On-Device Clerk (AFM)</span>
          <span class="vital-sub" id="clerkMeta">Apple Foundation Models</span>
        </div>
        <div class="standup-box" id="standupContent">
          <div class="headline-box" id="standupHeadline">Loading synthesized standup...</div>
          <div>
            <div class="standup-section-title">What Happened</div>
            <ul class="standup-list" id="standupHappened"></ul>
          </div>
          <div>
            <div class="standup-section-title">Open Threads</div>
            <ul class="standup-list" id="standupOpen"></ul>
          </div>
        </div>
      </div>
    </div>
  </main>

  <script>
    const APP_COLORS = {
      "com.apple.Terminal": "#34c759",
      "com.operasoftware.Opera": "#ff3b30",
      "com.nousresearch.hermes": "#c48b5e",
      "com.apple.finder": "#0a84ff",
      "com.apple.MobileSMS": "#30d158",
      "com.apple.pixelmator": "#af52de",
      "com.apple.mail": "#5e5ce6",
      "com.apple.Safari": "#007aff",
      "com.electron.ollama": "#ffd60a",
      "com.openai.codex": "#64d2ff"
    };

    function getAppColor(app) {
      if (APP_COLORS[app]) return APP_COLORS[app];
      let hash = 0;
      for (let i = 0; i < (app || "").length; i++) hash = app.charCodeAt(i) + ((hash << 5) - hash);
      const c = (hash & 0x00FFFFFF).toString(16).toUpperCase();
      return "#" + "00000".substring(0, 6 - c.length) + c;
    }

    function formatApp(app) {
      if (!app) return "Unknown";
      const parts = app.split(".");
      return parts[parts.length - 1];
    }

    function formatDuration(seconds) {
      const h = Math.floor(seconds / 3600);
      const m = Math.floor((seconds % 3600) / 60);
      if (h > 0) return `${h}h ${m}m`;
      return `${m}m`;
    }

    function formatTime(iso) {
      if (!iso) return "";
      try {
        const d = new Date(iso);
        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      } catch (e) { return iso; }
    }

    function renderRedacted(title) {
      if (!title) return "<span style='color: var(--text-muted); italic;'>None</span>";
      return title.replace(/\\[([A-Z_]+)\\]/g, '<span class="redaction-badge">[$1]</span>');
    }

    async function loadStatus() {
      try {
        const res = await fetch("/api/status");
        const data = await res.json();
        document.getElementById("valEvents").textContent = (data.events || 0).toLocaleString();
        document.getElementById("valActiveTime").textContent = formatDuration(data.active_seconds_lower_bound || 0);
        document.getElementById("valRedactions").textContent = `${data.redacted_events || 0} Clean`;

        // Render Ribbon
        const appSeconds = data.active_seconds_by_app || {};
        const total = Object.values(appSeconds).reduce((a, b) => a + b, 0) || 1;
        const ribbon = document.getElementById("ribbonBar");
        const legend = document.getElementById("ribbonLegend");
        ribbon.innerHTML = "";
        legend.innerHTML = "";

        const sortedApps = Object.entries(appSeconds).sort((a, b) => b[1] - a[1]);
        for (const [app, sec] of sortedApps.slice(0, 8)) {
          const pct = ((sec / total) * 100).toFixed(1);
          const color = getAppColor(app);
          const seg = document.createElement("div");
          seg.className = "ribbon-segment";
          seg.style.width = `${pct}%`;
          seg.style.background = color;
          seg.title = `${formatApp(app)} (${app}): ${formatDuration(sec)} (${pct}%)`;
          ribbon.appendChild(seg);

          const leg = document.createElement("div");
          leg.className = "legend-item";
          leg.innerHTML = `<span class="legend-color" style="background: ${color};"></span><span>${formatApp(app)} (${formatDuration(sec)})</span>`;
          legend.appendChild(leg);
        }
      } catch (e) {
        console.error("Failed to load status:", e);
      }
    }

    async function loadRecentEvents() {
      try {
        const res = await fetch("/api/recent?limit=40");
        const data = await res.json();
        const container = document.getElementById("eventsList");
        container.innerHTML = "";

        for (const ev of data.events || []) {
          const row = document.createElement("div");
          row.className = "event-row";
          row.innerHTML = `
            <div class="event-meta">
              <span class="app-badge" style="border-left: 3px solid ${getAppColor(ev.app)}">${formatApp(ev.app)}</span>
              <span>${formatTime(ev.observed_at)}</span>
            </div>
            <div class="event-title">${renderRedacted(ev.title)}</div>
          `;
          container.appendChild(row);
        }
      } catch (e) {
        console.error("Failed to load recent events:", e);
      }
    }

    async function loadStandup() {
      try {
        const res = await fetch("/api/standup", { method: "POST" });
        const data = await res.json();
        if (data.standup) {
          document.getElementById("standupHeadline").textContent = data.standup.headline || "Workstream activity summarized.";
          const happenedList = document.getElementById("standupHappened");
          happenedList.innerHTML = (data.standup.happened || []).map(h => `<li>${h}</li>`).join("");
          const openList = document.getElementById("standupOpen");
          openList.innerHTML = (data.standup.open || []).map(o => `<li>${o}</li>`).join("");
        } else if (data.report) {
          document.getElementById("standupHeadline").textContent = "Recent activity captured locally.";
          document.getElementById("standupHappened").innerHTML = `<li>Total events: ${data.report.events}</li><li>Active time: ${formatDuration(data.report.active_seconds_lower_bound)}</li>`;
          document.getElementById("standupOpen").innerHTML = `<li>Standup clerk ready for invocation</li>`;
        }
      } catch (e) {
        console.error("Failed to load standup:", e);
      }
    }

    async function triggerStandup() {
      const btn = document.getElementById("clerkBtn");
      btn.disabled = true;
      btn.textContent = "Synthesizing...";
      await loadStandup();
      btn.disabled = false;
      btn.innerHTML = "<span>⚡</span> Run AFM Clerk";
    }

    async function handleSearch(e) {
      if (e.key === "Enter") {
        const q = e.target.value.trim();
        if (!q) return closeSearch();
        try {
          const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
          const data = await res.json();
          const box = document.getElementById("searchBox");
          const list = document.getElementById("searchResultsList");
          box.style.display = "block";
          list.innerHTML = "";
          if ((data.matches || []).length === 0) {
            list.innerHTML = `<div style="padding: 10px; color: var(--text-muted);">No matches found for "${q}".</div>`;
            return;
          }
          for (const ev of data.matches) {
            const row = document.createElement("div");
            row.className = "event-row";
            row.innerHTML = `
              <div class="event-meta">
                <span class="app-badge">${formatApp(ev.app)}</span>
                <span>${formatTime(ev.observed_at)}</span>
              </div>
              <div class="event-title">${renderRedacted(ev.title)}</div>
            `;
            list.appendChild(row);
          }
        } catch (err) {
          console.error("Search failed:", err);
        }
      }
    }

    function closeSearch() {
      document.getElementById("searchBox").style.display = "none";
    }

    function loadAllData() {
      loadStatus();
      loadRecentEvents();
    }

    // Initial hydration
    loadAllData();
    loadStandup();
    // Auto-refresh stream every 8s
    setInterval(loadAllData, 8000);
  </script>
</body>
</html>
"""


class WholeMCPHandler:
    def __init__(self, db_path: Path, trail_path: Path, health_checker=None):
        self.db_path = Path(db_path).expanduser()
        self.trail_path = Path(trail_path).expanduser()
        self.repo_dir = _SCRIPTS_DIR.parent
        self.clerk_bin = self.repo_dir / ".build/debug/whole-clerk"
        self.health_checker = health_checker or health_report

    def _get_store(self) -> Store:
        return Store(self.db_path)

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "whole_status",
                "description": "Get current health, total recorded observations, active work time, and redaction counts from Whole's evidence store.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            },
            {
                "name": "whole_health",
                "description": "Run a read-only runtime check for Whole's plist, launchd registration, collector process, trail freshness, and Accessibility access.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            },
            {
                "name": "whole_search",
                "description": "Full-text search (FTS5) across past sanitized window titles, application activity, and paths recorded in Whole.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query keywords (e.g. 'Terminal', 'cargo build', 'getadongle.com')",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results to return (default 20)",
                            "default": 20,
                        },
                        "since_hours": {
                            "type": "integer",
                            "description": "Optional: only search events within the last N hours",
                        },
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "whole_timeline",
                "description": "Query active workstream timeline segments (application focus intervals, state, and durations).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "since_hours": {
                            "type": "integer",
                            "description": "Lookback window in hours (optional)",
                        },
                        "app": {
                            "type": "string",
                            "description": "Optional: filter by application bundle ID (e.g. 'com.apple.Terminal')",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum segments to return (default 50)",
                            "default": 50,
                        },
                    },
                    "additionalProperties": False,
                },
            },
            {
                "name": "whole_recent_events",
                "description": "Fetch recent chronologically ordered sanitized events from Whole's journal/store.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Maximum events to return (default 25)",
                            "default": 25,
                        },
                        "since_hours": {
                            "type": "integer",
                            "description": "Optional: only fetch events within the last N hours",
                        },
                        "app": {
                            "type": "string",
                            "description": "Optional: filter by application bundle ID",
                        },
                    },
                    "additionalProperties": False,
                },
            },
            {
                "name": "whole_standup",
                "description": "Run Whole's clerk (Apple Foundation Models on macOS, or configured local/remote provider) to synthesize a workstream standup from recent activity.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "provider": {
                            "type": "string",
                            "description": "Clerk provider: 'apple' (default), 'ollama', 'openrouter', or 'openai-compatible'",
                            "default": "apple",
                        },
                        "model": {
                            "type": "string",
                            "description": "Optional model name when using ollama or openai-compatible",
                        },
                    },
                    "additionalProperties": False,
                },
            },
        ]

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], bool]:
        """Execute a tool call and return (content_list, is_error)."""
        store = None
        try:
            if name == "whole_health":
                report = self.health_checker()
                return [{"type": "text", "text": json.dumps(report, ensure_ascii=False, indent=2)}], False

            store = self._get_store()
            if name == "whole_status":
                report = store.report()
                return [{"type": "text", "text": json.dumps(report, ensure_ascii=False, indent=2)}], False

            elif name == "whole_search":
                query = arguments.get("query", "")
                if not query:
                    return [{"type": "text", "text": "Error: 'query' parameter is required."}], True
                limit = int(arguments.get("limit", 20))
                since_hours = arguments.get("since_hours")
                if since_hours is not None:
                    since_hours = int(since_hours)
                results = store.search(query, limit=limit, since_hours=since_hours)
                return [{"type": "text", "text": json.dumps({"query": query, "count": len(results), "matches": results}, ensure_ascii=False, indent=2)}], False

            elif name == "whole_timeline":
                limit = int(arguments.get("limit", 50))
                since_hours = arguments.get("since_hours")
                if since_hours is not None:
                    since_hours = int(since_hours)
                app = arguments.get("app")
                segments = store.timeline(limit=limit, since_hours=since_hours, app=app)
                return [{"type": "text", "text": json.dumps({"count": len(segments), "segments": segments}, ensure_ascii=False, indent=2)}], False

            elif name == "whole_recent_events":
                limit = int(arguments.get("limit", 25))
                since_hours = arguments.get("since_hours")
                if since_hours is not None:
                    since_hours = int(since_hours)
                app = arguments.get("app")
                events = store.recent_events(limit=limit, since_hours=since_hours, app=app)
                return [{"type": "text", "text": json.dumps({"count": len(events), "events": events}, ensure_ascii=False, indent=2)}], False

            elif name == "whole_standup":
                provider = arguments.get("provider", "apple")
                model = arguments.get("model")
                if not self.trail_path.exists():
                    return [{"type": "text", "text": f"Error: trail journal not found at {self.trail_path}"}], True

                if self.clerk_bin.exists():
                    cmd = [str(self.clerk_bin), "--trail", str(self.trail_path), "--json", "--provider", provider]
                    if model:
                        cmd.extend(["--model", model])
                    env = dict(os.environ)
                    env["DEVELOPER_DIR"] = "/Applications/Xcode-beta.app/Contents/Developer"
                    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30, env=env)
                    if proc.returncode == 0:
                        return [{"type": "text", "text": proc.stdout.strip()}], False
                    else:
                        err_msg = proc.stderr.strip() or f"clerk exited with code {proc.returncode}"
                        return [{"type": "text", "text": f"Clerk execution error: {err_msg}"}], True
                else:
                    report = store.report()
                    recent = store.recent_events(limit=10)
                    summary = {
                        "clerk": "python-fallback",
                        "note": f"Swift clerk binary not found at {self.clerk_bin}. Run `make build` in ~/Developer/whole to compile.",
                        "report": report,
                        "recent_activity": recent,
                    }
                    return [{"type": "text", "text": json.dumps(summary, ensure_ascii=False, indent=2)}], False

            else:
                return [{"type": "text", "text": f"Unknown tool: {name}"}], True

        except Exception as exc:
            return [{"type": "text", "text": f"Internal tool execution error: {exc}"}], True
        finally:
            if store is not None:
                store.close()

    def handle_rpc(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a single JSON-RPC request and return the response dictionary."""
        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})

        if not method:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32600, "message": "Invalid Request: missing method"},
            }

        if req_id is None:
            if method == "notifications/initialized":
                pass
            return None

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {
                        "tools": {},
                    },
                    "serverInfo": {
                        "name": SERVER_NAME,
                        "version": SERVER_VERSION,
                    },
                },
            }

        elif method == "ping":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {},
            }

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": self.get_tool_definitions(),
                },
            }

        elif method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            content, is_error = self.call_tool(tool_name, tool_args)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": content,
                    "isError": is_error,
                },
            }

        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}",
                },
            }


def run_stdio(handler: WholeMCPHandler) -> None:
    """Run JSON-RPC over stdin / stdout."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = handler.handle_rpc(req)
            if resp is not None:
                sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
                sys.stdout.flush()
        except json.JSONDecodeError as exc:
            err_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {exc}"},
            }
            sys.stdout.write(json.dumps(err_resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


class SSESessionManager:
    def __init__(self):
        self.sessions: Dict[str, Tuple[BaseHTTPRequestHandler, threading.Event]] = {}
        self.lock = threading.Lock()

    def register(self, session_id: str, handler: BaseHTTPRequestHandler, done_event: threading.Event) -> None:
        with self.lock:
            self.sessions[session_id] = (handler, done_event)

    def unregister(self, session_id: str) -> None:
        with self.lock:
            self.sessions.pop(session_id, None)

    def send_message(self, session_id: str, message: Dict[str, Any]) -> bool:
        with self.lock:
            entry = self.sessions.get(session_id)
            if not entry:
                return False
            handler, _ = entry
            try:
                payload = f"event: message\ndata: {json.dumps(message, ensure_ascii=False)}\n\n"
                handler.wfile.write(payload.encode("utf-8"))
                handler.wfile.flush()
                return True
            except Exception:
                return False


def create_http_server(mcp_handler: WholeMCPHandler, host: str, port: int) -> ThreadingHTTPServer:
    session_manager = SSESessionManager()

    class MCPHTTPRequestHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            pass

        def do_GET(self) -> None:
            parsed = urlparse(self.path)

            # 1. Web Dashboard GUI Root
            if parsed.path == "/" or parsed.path == "/index.html":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(_DASHBOARD_HTML.encode("utf-8"))
                return

            # 2. Runtime health endpoint
            if parsed.path == "/health":
                report = mcp_handler.health_checker()
                report["status"] = "ok" if report.get("overall") == "healthy" else report.get("overall", "unknown")
                report["server"] = SERVER_NAME
                report["version"] = SERVER_VERSION
                report["protocolVersion"] = PROTOCOL_VERSION
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps(report, ensure_ascii=False).encode("utf-8"))
                return

            # 3. Store report endpoint for the dashboard
            if parsed.path == "/api/status" or parsed.path == "/status":
                store = mcp_handler._get_store()
                try:
                    report = store.report()
                    report["status"] = "ok"
                    report["server"] = SERVER_NAME
                    report["version"] = SERVER_VERSION
                    report["protocolVersion"] = PROTOCOL_VERSION
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps(report, ensure_ascii=False).encode("utf-8"))
                finally:
                    store.close()
                return

            if parsed.path == "/api/timeline":
                q = parse_qs(parsed.query)
                limit = int(q.get("limit", [100])[0])
                since_hours = q.get("since_hours", [None])[0]
                if since_hours is not None:
                    since_hours = int(since_hours)
                app = q.get("app", [None])[0]
                store = mcp_handler._get_store()
                try:
                    segments = store.timeline(limit=limit, since_hours=since_hours, app=app)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"count": len(segments), "segments": segments}, ensure_ascii=False).encode("utf-8"))
                finally:
                    store.close()
                return

            if parsed.path == "/api/recent":
                q = parse_qs(parsed.query)
                limit = int(q.get("limit", [50])[0])
                since_hours = q.get("since_hours", [None])[0]
                if since_hours is not None:
                    since_hours = int(since_hours)
                app = q.get("app", [None])[0]
                store = mcp_handler._get_store()
                try:
                    events = store.recent_events(limit=limit, since_hours=since_hours, app=app)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"count": len(events), "events": events}, ensure_ascii=False).encode("utf-8"))
                finally:
                    store.close()
                return

            if parsed.path == "/api/search":
                q = parse_qs(parsed.query)
                query_str = q.get("q", [""])[0] or q.get("query", [""])[0]
                limit = int(q.get("limit", [20])[0])
                store = mcp_handler._get_store()
                try:
                    results = store.search(query_str, limit=limit) if query_str else []
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"query": query_str, "count": len(results), "matches": results}, ensure_ascii=False).encode("utf-8"))
                finally:
                    store.close()
                return

            # 3. SSE endpoint for MCP & live event stream
            if parsed.path == "/sse":
                session_id = str(uuid.uuid4())
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                endpoint_url = f"/message?session_id={session_id}"
                init_event = f"event: endpoint\ndata: {endpoint_url}\n\n"
                self.wfile.write(init_event.encode("utf-8"))
                self.wfile.flush()

                done_event = threading.Event()
                session_manager.register(session_id, self, done_event)
                try:
                    while not done_event.is_set():
                        time.sleep(15)
                        try:
                            self.wfile.write(b": keepalive\n\n")
                            self.wfile.flush()
                        except Exception:
                            break
                finally:
                    session_manager.unregister(session_id)
                return

            self.send_response(404)
            self.end_headers()

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"

            # API standup endpoint
            if parsed.path == "/api/standup":
                content, is_error = mcp_handler.call_tool("whole_standup", {})
                self.send_response(200 if not is_error else 500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(content[0]["text"].encode("utf-8"))
                return

            try:
                req = json.loads(body)
            except Exception as exc:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"Invalid JSON: {exc}"}).encode("utf-8"))
                return

            # Direct JSON-RPC endpoint
            if parsed.path in ("/rpc", "/jsonrpc"):
                resp = mcp_handler.handle_rpc(req)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                if resp is not None:
                    self.wfile.write(json.dumps(resp, ensure_ascii=False).encode("utf-8"))
                return

            # SSE Message endpoint
            if parsed.path in ("/message", "/messages"):
                query_params = parse_qs(parsed.query)
                session_id = query_params.get("session_id", [""])[0]
                resp = mcp_handler.handle_rpc(req)
                if resp is not None and session_id:
                    session_manager.send_message(session_id, resp)

                self.send_response(202)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                return

            self.send_response(404)
            self.end_headers()

        def do_OPTIONS(self) -> None:
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.end_headers()

    return ThreadingHTTPServer((host, port), MCPHTTPRequestHandler)


def main() -> int:
    parser = argparse.ArgumentParser(description="Whole MCP Server & Dashboard")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Path to SQLite whole.db")
    parser.add_argument("--trail", default=str(DEFAULT_TRAIL_PATH), help="Path to trail.jsonl")
    parser.add_argument("--stdio", action="store_true", help="Run in stdio mode (default if no network args)")
    parser.add_argument("--sse", action="store_true", help="Run in HTTP/SSE server mode")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Host to bind HTTP/SSE server (default: {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Port to bind HTTP/SSE server (default: {DEFAULT_PORT})")
    args = parser.parse_args()

    handler = WholeMCPHandler(Path(args.db), Path(args.trail))

    if args.sse:
        server = create_http_server(handler, args.host, args.port)
        print(f"Whole MCP & Dashboard running on http://{args.host}:{args.port}/", file=sys.stderr)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down Whole MCP server...", file=sys.stderr)
            server.server_close()
        return 0
    else:
        run_stdio(handler)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
