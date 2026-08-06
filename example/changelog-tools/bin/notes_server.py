#!/usr/bin/env python3
"""Minimal MCP stdio server. It stores release notes in the file named by NOTES_FILE.

The client sets PLUGIN_ROOT and PLUGIN_DATA. The mcp.json file expands ${PLUGIN_DATA}
into NOTES_FILE. This server never writes inside PLUGIN_ROOT, because a plugin update
replaces the package contents.
ponytail: line-delimited JSON-RPC, stdlib only. Use an MCP SDK if the tool set grows.
"""
import json
import os
import sys

PROTOCOL = "2025-06-18"
NOTES_FILE = os.environ.get("NOTES_FILE") or os.path.join(
    os.environ.get("PLUGIN_DATA", "."), "notes.jsonl"
)

TOOLS = [
    {
        "name": "add_note",
        "description": "Append one release note.",
        "inputSchema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    {
        "name": "list_notes",
        "description": "List every stored release note.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def add_note(text):
    os.makedirs(os.path.dirname(NOTES_FILE) or ".", exist_ok=True)
    with open(NOTES_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps({"text": text}) + "\n")
    return f"stored: {text}"


def list_notes():
    if not os.path.exists(NOTES_FILE):
        return "no notes"
    with open(NOTES_FILE, encoding="utf-8") as f:
        return "\n".join(json.loads(line)["text"] for line in f if line.strip())


def handle(req):
    """Return a JSON-RPC response dict, or None for a notification."""
    method, rid = req.get("method"), req.get("id")
    if method == "initialize":
        result = {
            "protocolVersion": PROTOCOL,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "notes", "version": "1.0.0"},
        }
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        params = req.get("params", {})
        name = params.get("name")
        args = params.get("arguments", {})
        if name == "add_note":
            text = add_note(args.get("text", ""))
        elif name == "list_notes":
            text = list_notes()
        else:
            return {"jsonrpc": "2.0", "id": rid,
                    "error": {"code": -32602, "message": f"unknown tool: {name}"}}
        result = {"content": [{"type": "text", "text": text}]}
    elif rid is None:
        return None
    else:
        return {"jsonrpc": "2.0", "id": rid,
                "error": {"code": -32601, "message": f"unknown method: {method}"}}
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def demo():
    init = handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"}) or {}
    assert init["result"]["protocolVersion"] == PROTOCOL
    tools = handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}) or {}
    assert len(tools["result"]["tools"]) == 2
    assert handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    assert "error" in (handle({"jsonrpc": "2.0", "id": 3, "method": "nope"}) or {})
    print("notes_server self-check passed")


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        resp = handle(json.loads(line))
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        demo()
    else:
        main()
