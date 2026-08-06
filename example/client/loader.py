#!/usr/bin/env python3
"""Reference Agent Plugins v1.0.0 client loader.

The loader reads a plugin directory. It returns the discovered skills and the MCP
server launch plans. It applies the failure boundaries of the specification: a fault
in one component never removes an independent component.

Run the self-check:
    python loader.py

Load the example plugin:
    python loader.py ../changelog-tools
"""
import json
import os
import re
import sys

PLUGIN_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
MCP_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"

MANIFEST_FIELDS = {
    "$schema": str, "name": str, "version": str, "description": str,
    "author": dict, "homepage": str, "repository": str, "license": str,
    "keywords": list, "extensions": dict,
}
AUTHOR_FIELDS = {"name", "email", "url"}
NAME_RE = re.compile(r"^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")
PLACEHOLDER_RE = re.compile(r"\$\{PLUGIN_ROOT\}|\$\{PLUGIN_DATA\}")
CWD_RE = re.compile(r"^(?:\./|\$\{PLUGIN_ROOT\}(?:/|$)|\$\{PLUGIN_DATA\}(?:/|$))")
LOOPBACK_RE = re.compile(r"^(?:localhost|127(?:\.\d+){3}|\[::1\])$", re.I)


class Fatal(Exception):
    """A manifest violation that rejects the whole plugin (spec 5.3, 11.3)."""


def contained(path, root):
    """Return True when path stays inside root after symlink resolution (spec 4.1)."""
    rp, rr = os.path.realpath(path), os.path.realpath(root)
    return rp == rr or rp.startswith(rr + os.sep)


def expand(value, plugin_root, plugin_data):
    """Replace ${PLUGIN_ROOT} and ${PLUGIN_DATA} in one pass (spec 9.2).

    The replacement text is never scanned again. No other variable expands.
    """
    table = {"${PLUGIN_ROOT}": plugin_root, "${PLUGIN_DATA}": plugin_data}
    return PLACEHOLDER_RE.sub(lambda m: table[m.group(0)], value)


def resolve_rel(value, root):
    """Resolve a plugin-relative './x' path against root. Return None if it escapes."""
    if not value.startswith("./"):
        return None
    path = os.path.join(root, value[2:])
    return path if contained(path, root) else None


# --- step 2: manifest -------------------------------------------------------

def load_manifest(root, report):
    """Read and validate plugin.json. Raise Fatal to reject the plugin (spec 5)."""
    path = os.path.join(root, "plugin.json")
    if not contained(path, root):
        raise Fatal("plugin.json resolves outside the plugin root")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise Fatal("plugin.json is missing")
    except json.JSONDecodeError as e:
        raise Fatal(f"plugin.json is not valid JSON: {e}")
    if not isinstance(data, dict):
        raise Fatal("plugin.json is not a JSON object")

    for key in list(data):
        if key not in MANIFEST_FIELDS:
            report(f"unknown manifest field ignored: {key}")   # non-fatal, spec 5.2
            del data[key]

    if data.get("$schema") != PLUGIN_SCHEMA:
        raise Fatal(f"unsupported $schema: {data.get('$schema')!r}")
    name = data.get("name")
    if not isinstance(name, str) or not (1 <= len(name) <= 64) or not NAME_RE.match(name):
        raise Fatal(f"invalid name: {name!r}")

    for key, kind in MANIFEST_FIELDS.items():
        if key in data and not isinstance(data[key], kind):
            if key == "extensions":
                report("extensions is not an object; field ignored")  # non-fatal, spec 8.1
                data["extensions"] = {}
            else:
                raise Fatal(f"field {key} has the wrong type")
    if isinstance(data.get("keywords"), list) and not all(
            isinstance(k, str) for k in data["keywords"]):
        raise Fatal("keywords must contain strings only")
    author = data.get("author")
    if isinstance(author, dict):
        for key, val in author.items():
            if key not in AUTHOR_FIELDS or not isinstance(val, str):
                raise Fatal(f"invalid author field: {key}")
    for ns, val in data.get("extensions", {}).items():
        if not isinstance(val, dict):
            raise Fatal(f"extensions.{ns} is not an object")
    return data


# --- step 4a: skills --------------------------------------------------------

def discover_skills(root, report):
    """Return the skill directories under skills/ (spec 6.1, 7.1)."""
    base = os.path.join(root, "skills")
    if not os.path.exists(base):
        return []                                   # missing is not an error, spec 6.2
    if not os.path.isdir(base):
        report("skills exists but is not a directory; skills disabled")
        return []
    skills = []
    for entry in sorted(os.listdir(base)):          # immediate children only, spec 7.1
        skill_md = os.path.join(base, entry, "SKILL.md")
        if not os.path.isfile(skill_md):
            continue
        if not contained(skill_md, root):
            report(f"skill {entry} escapes the plugin root; skipped")
            continue
        skills.append({"name": entry, "path": skill_md})
    return skills


# --- step 4b: MCP servers ---------------------------------------------------

def validate_server(entry, root, plugin_data):
    """Return a launch plan, or raise ValueError for an invalid entry (spec 7.2)."""
    if not isinstance(entry, dict) or "type" not in entry:
        raise ValueError("server entry has no type")
    kind = entry["type"]

    if kind == "stdio":
        allowed = {"type", "command", "args", "env", "cwd"}
        extra = set(entry) - allowed
        if extra:
            raise ValueError(f"unknown stdio fields: {sorted(extra)}")
        command = entry.get("command")
        if not isinstance(command, str) or not command:
            raise ValueError("command is missing")
        if command.startswith("./"):
            resolved = resolve_rel(command, root)
            if resolved is None:
                raise ValueError("command escapes the plugin root")
            command = resolved
        elif "/" in command or "\\" in command:
            raise ValueError("command must be a bare name or a ./ path")
        args = entry.get("args", [])
        if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
            raise ValueError("args must be a list of strings")
        env = entry.get("env", {})
        if not isinstance(env, dict) or not all(
                isinstance(k, str) and isinstance(v, str) for k, v in env.items()):
            raise ValueError("env must be an object of strings")
        if "PLUGIN_ROOT" in env or "PLUGIN_DATA" in env:
            raise ValueError("env must not set PLUGIN_ROOT or PLUGIN_DATA")  # spec 9.2
        cwd = entry.get("cwd")
        if cwd is None:
            cwd_path = root                                   # default, spec 7.2.1
        else:
            if not isinstance(cwd, str) or not CWD_RE.match(cwd):
                raise ValueError(f"invalid cwd form: {cwd!r}")
            cwd_path = os.path.normpath(expand(
                cwd if not cwd.startswith("./") else os.path.join(root, cwd[2:]),
                root, plugin_data))
            base = plugin_data if cwd.startswith("${PLUGIN_DATA}") else root
            if not contained(cwd_path, base):
                raise ValueError("cwd escapes its base directory")
        # The client sets the reserved variables last (spec 9.1).
        final_env = {k: expand(v, root, plugin_data) for k, v in env.items()}
        final_env["PLUGIN_ROOT"] = root
        final_env["PLUGIN_DATA"] = plugin_data
        return {"type": "stdio", "command": command,
                "args": [expand(a, root, plugin_data) for a in args],
                "env": final_env, "cwd": cwd_path}

    if kind in ("streamable-http", "sse"):
        allowed = {"type", "url", "headers"}
        extra = set(entry) - allowed
        if extra:
            raise ValueError(f"unknown {kind} fields: {sorted(extra)}")
        url = entry.get("url")
        if not isinstance(url, str):
            raise ValueError("url is missing")
        m = re.match(r"^(https?)://([^/?#]+)(?:[/?#]|$)", url, re.I)
        if not m:
            raise ValueError("url must be an absolute http or https URL")
        scheme, host = m.group(1).lower(), m.group(2)
        if "@" in host:
            raise ValueError("url must not contain user information")
        if "#" in url:
            raise ValueError("url must not contain a fragment")
        hostname = host.split(":")[0]
        if scheme == "http" and not LOOPBACK_RE.match(hostname):
            raise ValueError("http is allowed for a loopback host only")
        headers = entry.get("headers", {})
        if not isinstance(headers, dict) or not all(
                isinstance(k, str) and isinstance(v, str) for k, v in headers.items()):
            raise ValueError("headers must be an object of strings")
        lowered = [k.lower() for k in headers]
        if len(set(lowered)) != len(lowered):
            raise ValueError("duplicate header name under different casing")
        # No expansion in url or headers (spec 7.2.1).
        return {"type": kind, "url": url, "headers": dict(headers)}

    raise ValueError(f"unknown transport: {kind!r}")


def load_mcp(root, manifest_schema, plugin_data, report, transports=("stdio", "streamable-http")):
    """Return the valid server plans from mcp.json (spec 7.2.2)."""
    path = os.path.join(root, "mcp.json")
    if not os.path.exists(path):
        return {}
    if not os.path.isfile(path):
        report("mcp.json exists but is not a regular file; MCP disabled")
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        report(f"mcp.json is not valid JSON: {e}; MCP disabled")
        return {}
    if not isinstance(data, dict) or set(data) != {"$schema", "mcpServers"}:
        report("mcp.json has wrong top-level fields; MCP disabled")
        return {}
    if data["$schema"] != MCP_SCHEMA:
        report("mcp.json targets an unsupported version; MCP disabled")
        return {}
    if data["$schema"].rsplit("/", 2)[1] != manifest_schema.rsplit("/", 2)[1]:
        report("mcp.json version differs from plugin.json; MCP disabled")  # spec 10.1
        return {}
    if not isinstance(data["mcpServers"], dict):
        report("mcpServers is not an object; MCP disabled")
        return {}

    plans = {}
    for name, entry in data["mcpServers"].items():
        try:
            plan = validate_server(entry, root, plugin_data)
        except ValueError as e:
            report(f"server {name} skipped: {e}")       # per-entry boundary, spec 7.2.2
            continue
        if plan["type"] not in transports:
            report(f"server {name} skipped: transport {plan['type']} is unsupported")
            continue
        plans[name] = plan
    return plans


def load_plugin(root, plugin_data=None, transports=("stdio", "streamable-http")):
    """Load one plugin directory. Return a dict, or raise Fatal to reject the plugin."""
    root = os.path.realpath(root)
    # PLUGIN_DATA lives outside the package. A plugin update replaces the package
    # contents, and the data directory must survive that update (spec 9.1).
    default_data = os.path.join(os.path.dirname(root), ".plugin-data", os.path.basename(root))
    plugin_data = os.path.realpath(plugin_data or default_data)
    os.makedirs(plugin_data, exist_ok=True)            # spec 9.1
    reports = []
    manifest = load_manifest(root, reports.append)
    return {
        "name": manifest["name"],
        "manifest": manifest,
        "skills": discover_skills(root, reports.append),
        "servers": load_mcp(root, manifest["$schema"], plugin_data, reports.append, transports),
        "extensions": manifest.get("extensions", {}),
        "reports": reports,
    }


# --- self-check -------------------------------------------------------------

def demo():
    import tempfile

    def write(base, rel, text):
        path = os.path.join(base, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    with tempfile.TemporaryDirectory() as tmp:
        root = os.path.join(tmp, "p")
        write(root, "plugin.json", json.dumps({
            "$schema": PLUGIN_SCHEMA, "name": "demo.plugin", "nope": 1,
            "extensions": {"com.example.client": {"a": 1}}}))
        write(root, "skills/one/SKILL.md", "---\nname: one\ndescription: d\n---\n")
        write(root, "skills/two/README.md", "not a skill")
        write(root, "skills/one/nested/SKILL.md", "must not be discovered")
        write(root, "mcp.json", json.dumps({"$schema": MCP_SCHEMA, "mcpServers": {
            "ok": {"type": "stdio", "command": "python",
                   "args": ["${PLUGIN_ROOT}/bin/x.py"],
                   "env": {"D": "${PLUGIN_DATA}/d"}, "cwd": "${PLUGIN_DATA}"},
            "escape": {"type": "stdio", "command": "../evil"},
            "reserved": {"type": "stdio", "command": "x", "env": {"PLUGIN_ROOT": "/tmp"}},
            "plain_http": {"type": "streamable-http", "url": "http://example.com/mcp"},
            "local_http": {"type": "streamable-http", "url": "http://localhost:8080/mcp"},
            "legacy": {"type": "sse", "url": "https://legacy.example.com/sse"},
            "bogus": {"type": "websocket", "url": "wss://x"},
        }}))
        data_dir = os.path.join(tmp, "data")
        p = load_plugin(root, data_dir)

        assert p["name"] == "demo.plugin"
        assert "nope" not in p["manifest"], "unknown field must be dropped"
        assert any("unknown manifest field" in r for r in p["reports"])
        assert [s["name"] for s in p["skills"]] == ["one"], p["skills"]
        assert set(p["servers"]) == {"ok", "local_http"}, set(p["servers"])
        assert p["servers"]["ok"]["args"] == [root + "/bin/x.py"], p["servers"]["ok"]["args"]
        assert p["servers"]["ok"]["env"]["PLUGIN_ROOT"] == root
        assert p["servers"]["ok"]["env"]["D"].startswith(data_dir)
        assert p["servers"]["ok"]["cwd"] == os.path.realpath(data_dir)
        assert any("legacy" in r and "unsupported" in r for r in p["reports"])

        # A single non-recursive expansion pass.
        assert expand("${PLUGIN_ROOT}", "${PLUGIN_DATA}", "/d") == "${PLUGIN_DATA}"
        assert expand("a${PLUGIN_ROOT}b${PLUGIN_DATA}c", "/r", "/d") == "a/rb/dc"
        assert expand("${OTHER}", "/r", "/d") == "${OTHER}"

        # Fatal manifest cases.
        for bad in [{"name": "x"},
                    {"$schema": PLUGIN_SCHEMA},
                    {"$schema": PLUGIN_SCHEMA, "name": "Bad-Name"},
                    {"$schema": PLUGIN_SCHEMA, "name": "has--double"},
                    {"$schema": PLUGIN_SCHEMA, "name": "-lead"},
                    {"$schema": "https://example.com/other.json", "name": "x"},
                    {"$schema": PLUGIN_SCHEMA, "name": "x", "keywords": "no"},
                    {"$schema": PLUGIN_SCHEMA, "name": "x", "author": {"nick": "n"}}]:
            write(root, "plugin.json", json.dumps(bad))
            try:
                load_plugin(root, data_dir)
                raise AssertionError(f"expected rejection: {bad}")
            except Fatal:
                pass

        # A non-object extensions field is not fatal.
        write(root, "plugin.json", json.dumps(
            {"$schema": PLUGIN_SCHEMA, "name": "x", "extensions": "no"}))
        p2 = load_plugin(root, data_dir)
        assert p2["extensions"] == {}
        assert any("extensions is not an object" in r for r in p2["reports"])

    print("loader self-check passed")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        result = load_plugin(sys.argv[1])
        print(json.dumps(result, indent=2))
    else:
        demo()
