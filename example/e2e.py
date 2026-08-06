#!/usr/bin/env python3
"""End-to-end demonstration: the tutorial example really runs.

Part A launches the plugin through the reference client and speaks MCP to it.
Part B checks that the code in the HTML pages matches the files in this directory.

Run it:
    python example/e2e.py          # both parts
    python example/e2e.py --quiet  # results only, no MCP transcript

The script needs Python only. The cross-client check needs Node and npm; it
reports "skipped" without them. Exit code 0 means every check passed.
ponytail: one file, stdlib only. Split it when a third part appears.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PLUGIN = os.path.join(HERE, "changelog-tools")
CLIENT = os.path.join(HERE, "client")
PAGES = ["index.html", "plugin-authors.html", "client-implementers.html", "reference.html"]

QUIET = "--quiet" in sys.argv
PASS, FAIL = [], []


def check(label, ok, detail=""):
    (PASS if ok else FAIL).append(label)
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {label}" + (f" — {detail}" if detail else ""))
    return ok


def say(*parts):
    if not QUIET:
        print(*parts)


# --- MCP over stdio ---------------------------------------------------------

class Server:
    """One MCP stdio subprocess, started from a client launch plan."""

    def __init__(self, plan, label="notes"):
        # A real client layers the plugin env over its own environment. It does not
        # replace it: on Windows a process without SystemRoot or PATH cannot start.
        env = {**os.environ, **plan["env"]}
        self.label = label
        self.proc = subprocess.Popen(
            [plan["command"], *plan["args"]],
            cwd=plan["cwd"], env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", bufsize=1,
        )
        self._id = 0

    def send(self, method, params=None, notify=False):
        """Write one JSON-RPC line. Return the parsed response, or None for a notification."""
        req = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            req["params"] = params
        if not notify:
            self._id += 1
            req["id"] = self._id
        line = json.dumps(req)
        say(f"    -> {line}")
        self.proc.stdin.write(line + "\n")
        self.proc.stdin.flush()
        if notify:
            return None
        out = self.proc.stdout.readline()
        if not out:
            raise RuntimeError(f"{self.label}: the server closed stdout; "
                               f"stderr={self.proc.stderr.read()!r}")
        say(f"    <- {out.rstrip()}")
        return json.loads(out)

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=10)
        except Exception:
            self.proc.kill()


def snapshot(root):
    """Return {relative path: (size, mtime)} for every file under root."""
    out = {}
    for base, _dirs, files in os.walk(root):
        for f in files:
            p = os.path.join(base, f)
            st = os.stat(p)
            out[os.path.relpath(p, root)] = (st.st_size, st.st_mtime_ns)
    return out


# --- part A -----------------------------------------------------------------

def part_a():
    print("\n=== Part A: the plugin runs through the reference client ===")

    # 1. Load the plugin with the documented command (index.html, "Run the example").
    print("\n[A1] python loader.py ../changelog-tools")
    proc = subprocess.run([sys.executable, "loader.py", "../changelog-tools"],
                          cwd=CLIENT, capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        check("the Python loader loads the example plugin", False, proc.stderr.strip()[:300])
        return
    plugin = json.loads(proc.stdout)
    check("the Python loader loads the example plugin", True)
    check("the loader finds the skill changelog-entry",
          [s["name"] for s in plugin["skills"]] == ["changelog-entry"])
    check("the loader keeps the stdio and streamable-http servers",
          sorted(plugin["servers"]) == ["notes", "release-api"], str(sorted(plugin["servers"])))
    check("the loader skips the sse server and reports why",
          plugin["reports"] == ["server legacy-feed skipped: transport sse is unsupported"],
          str(plugin["reports"]))
    check("the client extension namespace survives the load",
          plugin["extensions"].get("com.example.client") == {"autoEnable": True})

    plan = plugin["servers"]["notes"]
    notes_file = plan["env"]["NOTES_FILE"]
    data_dir = plan["env"]["PLUGIN_DATA"]
    check("NOTES_FILE expands into PLUGIN_DATA, not into PLUGIN_ROOT",
          os.path.realpath(notes_file).startswith(os.path.realpath(data_dir))
          and not os.path.realpath(notes_file).startswith(os.path.realpath(plan["env"]["PLUGIN_ROOT"])))

    # A clean start makes the assertions below exact.
    if os.path.exists(notes_file):
        os.remove(notes_file)
    before = snapshot(PLUGIN)

    # 2. Launch the plan verbatim and speak MCP to it.
    print("\n[A2] launch the plan and speak MCP")
    say(f"    command: {plan['command']} {' '.join(plan['args'])}")
    say(f"    cwd:     {plan['cwd']}")
    server = Server(plan)
    try:
        init = server.send("initialize", {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "e2e", "version": "1.0.0"},
        })
        check("initialize returns the protocol version and the server name",
              init["result"]["protocolVersion"] == "2025-06-18"
              and init["result"]["serverInfo"]["name"] == "notes")

        server.send("notifications/initialized", notify=True)

        listed = server.send("tools/list")
        names = sorted(t["name"] for t in listed["result"]["tools"])
        check("tools/list returns add_note and list_notes", names == ["add_note", "list_notes"],
              str(names))

        empty = server.send("tools/call", {"name": "list_notes", "arguments": {}})
        check("list_notes reports an empty store before the first write",
              empty["result"]["content"][0]["text"] == "no notes")

        first = "Add a --json flag to the export command (#412)"
        added = server.send("tools/call", {"name": "add_note", "arguments": {"text": first}})
        check("add_note confirms the write",
              added["result"]["content"][0]["text"] == f"stored: {first}")

        second = "Fix the crash on an empty changelog file (#418)"
        server.send("tools/call", {"name": "add_note", "arguments": {"text": second}})

        both = server.send("tools/call", {"name": "list_notes", "arguments": {}})
        check("list_notes returns both notes in order",
              both["result"]["content"][0]["text"] == f"{first}\n{second}")

        bad = server.send("tools/call", {"name": "no_such_tool", "arguments": {}})
        check("an unknown tool returns a JSON-RPC error, and the server stays up",
              bad.get("error", {}).get("code") == -32602)
        still = server.send("tools/list")
        check("the server answers again after the error", len(still["result"]["tools"]) == 2)
    finally:
        server.close()

    # 3. Check the effect on disk.
    print("\n[A3] the effect on disk")
    check("notes.jsonl exists in PLUGIN_DATA", os.path.isfile(notes_file), notes_file)
    with open(notes_file, encoding="utf-8") as f:
        lines = [json.loads(x) for x in f if x.strip()]
    check("notes.jsonl holds both records as line-delimited JSON",
          [r["text"] for r in lines] == [first, second])
    after = snapshot(PLUGIN)
    check("the server wrote nothing inside PLUGIN_ROOT (spec §9.1)",
          before == after,
          "" if before == after
          else str(sorted(set(after) ^ set(before)) or "an existing file changed"))

    # 4. The data must survive a restart, because that is the point of PLUGIN_DATA.
    print("\n[A4] restart the server")
    server = Server(plan)
    try:
        server.send("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                   "clientInfo": {"name": "e2e", "version": "1.0.0"}})
        again = server.send("tools/call", {"name": "list_notes", "arguments": {}})
        check("the notes survive a restart of the server",
              again["result"]["content"][0]["text"] == f"{first}\n{second}")
    finally:
        server.close()

    # 5. The skill ships a script. Run it on a good file and on a bad file.
    print("\n[A5] the skill script scripts/check_entry.py")
    script = os.path.join(PLUGIN, "skills", "changelog-entry", "scripts", "check_entry.py")
    good = ("## [1.2.0] - 2026-08-06\n\n### Added\n"
            f"- {first}\n\n### Fixed\n- {second}\n")
    bad = ("## [1.2.0] - 2026-08-06\n\n### Fixed\n"
           f"- {second}\n\n### Added\n- {first}\n")
    with tempfile.TemporaryDirectory() as tmp:
        for label, text, want_code in (("valid", good, 0), ("out of order", bad, 1)):
            path = os.path.join(tmp, "CHANGELOG.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            r = subprocess.run([sys.executable, script, path],
                               capture_output=True, text=True, encoding="utf-8")
            say(f"    check_entry.py ({label}) -> exit {r.returncode} {r.stdout.strip()!r}")
            check(f"check_entry.py accepts a {label} entry" if want_code == 0
                  else f"check_entry.py rejects an entry that is {label}",
                  r.returncode == want_code)
        check("the rejection names the reason", "sections are out of order" in r.stdout)

    # 6. Both reference clients must produce the same plan.
    print("\n[A6] the TypeScript client produces the same plan")
    ts = run_ts_loader()
    if ts is None:
        print("  [SKIP] the TypeScript client needs Node and npm")
    else:
        check("both reference clients produce the same launch plan",
              normalize(ts) == normalize(plugin),
              first_difference(normalize(ts), normalize(plugin)))

    # 7. index.html calls this "the smallest valid plugin". Build it and load it.
    print("\n[A7] the smallest valid plugin from index.html")
    blocks = code_blocks("index.html")
    tree = next(b for b in blocks if b.lstrip().startswith("hello-plugin/"))
    tiny = next(b for b in blocks if '"hello-plugin"' in b)
    with tempfile.TemporaryDirectory() as tmp:
        root = os.path.join(tmp, "hello-plugin")
        for rel in parse_tree(tree):
            path = os.path.join(root, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            if rel.endswith("plugin.json"):
                with open(path, "w", encoding="utf-8") as f:
                    f.write(tiny.strip())
            elif rel.endswith("SKILL.md"):
                with open(path, "w", encoding="utf-8") as f:
                    f.write("---\nname: greet\ndescription: Greet the user.\n---\n\n# Greet\n")
        r = subprocess.run([sys.executable, "loader.py", root], cwd=CLIENT,
                           capture_output=True, text=True, encoding="utf-8")
        say(f"    loader.py <hello-plugin> -> exit {r.returncode}")
        if check("the smallest valid plugin loads", r.returncode == 0, r.stderr.strip()[:200]):
            small = json.loads(r.stdout)
            check("the smallest valid plugin needs no mcp.json", small["servers"] == {})
            check("its one skill is discovered",
                  [s["name"] for s in small["skills"]] == ["greet"])
            check("it produces no warning", small["reports"] == [], str(small["reports"]))

    # 8. Run every command the pages tell the reader to run.
    print("\n[A8] every documented command")
    npm = "npm.cmd" if os.name == "nt" else "npm"
    commands = [
        ("python loader.py", [sys.executable, "loader.py"], CLIENT, "loader self-check passed"),
        ("npm test", [npm, "test"], CLIENT, "loader self-check passed"),
        ("python bin/notes_server.py --self-check",
         [sys.executable, os.path.join("bin", "notes_server.py"), "--self-check"], PLUGIN,
         "notes_server self-check passed"),
        ("python scripts/check_entry.py",
         [sys.executable, os.path.join("skills", "changelog-entry", "scripts", "check_entry.py")],
         PLUGIN, "check_entry self-check passed"),
    ]
    for label, argv, cwd, expect in commands:
        try:
            r = subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                               encoding="utf-8", timeout=600)
        except (FileNotFoundError, subprocess.SubprocessError) as e:
            print(f"  [SKIP] {label} — {e}")
            continue
        say(f"    {label} -> exit {r.returncode}")
        check(f"{label} passes its self-check",
              r.returncode == 0 and expect in r.stdout,
              (r.stdout + r.stderr).strip()[-200:])


def run_ts_loader():
    """Return the TypeScript loader output for the example, or None when Node is absent."""
    npm = "npm.cmd" if os.name == "nt" else "npm"
    try:
        if not os.path.isdir(os.path.join(CLIENT, "node_modules")):
            say("    npm install")
            subprocess.run([npm, "install", "--no-audit", "--no-fund"], cwd=CLIENT,
                           capture_output=True, text=True, timeout=600, check=True)
        r = subprocess.run([npm, "run", "load-example", "--silent"], cwd=CLIENT,
                           capture_output=True, text=True, encoding="utf-8", timeout=600)
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return json.loads(r.stdout[r.stdout.index("{"):])


def normalize(obj):
    """Make two loader outputs comparable across path spelling."""
    if isinstance(obj, dict):
        return {k: normalize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [normalize(v) for v in obj]
    if isinstance(obj, str):
        s = obj.replace("\\", "/")
        return re.sub(r"^([A-Za-z]):/", lambda m: m.group(1).upper() + ":/", s)
    return obj


def first_difference(a, b, path="$"):
    """Return a short description of the first place two structures differ."""
    if type(a) is not type(b):
        return f"{path}: {type(a).__name__} vs {type(b).__name__}"
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                return f"{path}.{k}: present on one side only"
            d = first_difference(a[k], b[k], f"{path}.{k}")
            if d:
                return d
        return ""
    if isinstance(a, list):
        if len(a) != len(b):
            return f"{path}: length {len(a)} vs {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            d = first_difference(x, y, f"{path}[{i}]")
            if d:
                return d
        return ""
    return "" if a == b else f"{path}: {a!r} vs {b!r}"


# --- part B -----------------------------------------------------------------

def strip_jsonc(text):
    """Remove // and /* */ comments and trailing commas. Never touch a string."""
    out, i, n, in_str, esc = [], 0, len(text), False, False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(c)
        i += 1
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def parse_tree(text):
    """Return the paths named by an ASCII directory tree, without the root line."""
    paths, stack = [], []
    for line in text.strip().splitlines()[1:]:
        line = line.split("#")[0].rstrip()
        m = re.match(r"^([\s│]*)(?:├──|└──)\s*(.+)$", line)
        if not m:
            continue
        stack = stack[:len(m.group(1)) // 4]
        stack.append(m.group(2).strip().rstrip("/"))
        paths.append("/".join(stack))
    return paths


def code_blocks(page):
    """Return the text of every <pre> block on one tutorial page."""
    import html as htmlmod
    src = open(os.path.join(REPO, page), encoding="utf-8").read()
    raw = re.findall(r"<pre[^>]*>(?:\s*<code[^>]*>)?(.*?)(?:</code>\s*)?</pre>", src, re.S)
    return [htmlmod.unescape(re.sub(r"<[^>]+>", "", b)) for b in raw]


def part_b():
    print("\n=== Part B: the HTML pages show the files that exist ===")
    blocks = {p: code_blocks(p) for p in PAGES}
    author = blocks["plugin-authors.html"]

    # 1. The commented manifest must parse to the real plugin.json.
    manifest_blocks = [b for b in author if '"name": "changelog-tools"' in b and "$schema" in b]
    real_manifest = json.load(open(os.path.join(PLUGIN, "plugin.json"), encoding="utf-8"))
    if check("plugin-authors.html shows exactly one annotated plugin.json",
             len(manifest_blocks) == 1, f"found {len(manifest_blocks)}"):
        shown = json.loads(strip_jsonc(manifest_blocks[0]))
        check("the annotated plugin.json equals example/changelog-tools/plugin.json",
              shown == real_manifest, first_difference(shown, real_manifest))
        check("the annotated plugin.json uses all ten manifest keys",
              len(shown) == 10, str(sorted(shown)))

    # 2. The two mcp.json blocks are one file, split for the reader. Merge them.
    mcp_blocks = [b for b in author if '"mcpServers"' in b]
    real_mcp = json.load(open(os.path.join(PLUGIN, "mcp.json"), encoding="utf-8"))
    if check("plugin-authors.html shows the mcp.json file in two parts",
             len(mcp_blocks) == 2, f"found {len(mcp_blocks)}"):
        merged = {"$schema": None, "mcpServers": {}}
        for b in mcp_blocks:
            part = json.loads(strip_jsonc(b))
            merged["$schema"] = part["$schema"]
            merged["mcpServers"].update(part["mcpServers"])
        check("the two parts join into example/changelog-tools/mcp.json",
              merged == real_mcp, first_difference(merged, real_mcp))
        check("all three transports appear",
              sorted(t["type"] for t in merged["mcpServers"].values())
              == ["sse", "stdio", "streamable-http"])

    # 3. The name rule printed on the page must be the rule both loaders apply.
    printed = [b.strip() for b in author if b.strip().startswith("/^(?!")]
    py_src = open(os.path.join(CLIENT, "loader.py"), encoding="utf-8").read()
    ts_src = open(os.path.join(CLIENT, "loader.ts"), encoding="utf-8").read()
    py_re = re.search(r'NAME_RE = re\.compile\(r"(.+?)"\)', py_src).group(1)
    ts_re = re.search(r"const NAME_RE = /(.+?)/;", ts_src).group(1)
    if check("plugin-authors.html prints the name regex once", len(printed) == 1):
        check("the printed name regex is the one loader.py compiles",
              printed[0] == f"/{py_re}/", f"{printed[0]} vs /{py_re}/")
    check("loader.py and loader.ts apply the same name regex", py_re == ts_re,
          f"{py_re} vs {ts_re}")

    # 4. The excerpt of the MCP server must be a real fragment of the real file.
    server_src = open(os.path.join(PLUGIN, "bin", "notes_server.py"), encoding="utf-8").read()
    excerpt = [b for b in author if "NOTES_FILE = os.environ.get" in b]
    if check("plugin-authors.html shows the NOTES_FILE excerpt", len(excerpt) == 1):
        want = "\n".join(x.rstrip() for x in excerpt[0].strip().splitlines() if not x.startswith("#"))
        have = "\n".join(x.rstrip() for x in server_src.splitlines())
        check("the excerpt appears verbatim in bin/notes_server.py", want in have, want[:60])

    # 5. The skill frontmatter on the page must match SKILL.md. The page wraps the
    #    description over two lines for the column width; unwrap before comparing.
    skill_src = open(os.path.join(PLUGIN, "skills", "changelog-entry", "SKILL.md"),
                     encoding="utf-8").read()
    shown_skill = [b for b in author if b.lstrip().startswith("---\nname: changelog-entry")]
    if check("plugin-authors.html shows the SKILL.md frontmatter", len(shown_skill) == 1):
        def frontmatter(text):
            body = text.strip().split("---", 2)[1]
            flat = re.sub(r"\s+", " ", body).strip()
            name = re.search(r"name: (\S+)", flat).group(1)
            desc = re.search(r"description: (.*)$", flat).group(1).strip()
            return name, desc
        check("the shown frontmatter matches skills/changelog-entry/SKILL.md",
              frontmatter(shown_skill[0]) == frontmatter(skill_src),
              str(frontmatter(shown_skill[0])))

    # 6. Every npm script the pages name must exist in package.json.
    scripts = json.load(open(os.path.join(CLIENT, "package.json"), encoding="utf-8"))["scripts"]
    named = set()
    for page in PAGES:
        for b in blocks[page]:
            named.update(re.findall(r"^npm (?:run )?(\S+)", b, re.M))
    named.discard("install")
    check("every npm script the pages name exists in package.json",
          named <= set(scripts), f"named={sorted(named)} defined={sorted(scripts)}")
    for cmd in ["cd example/client", "npm install", "npm test", "npm run load-example",
                "python loader.py ../changelog-tools"]:
        check(f"index.html prints the command: {cmd}",
              any(cmd in b for b in blocks["index.html"]))

    # 7. The directory tree on the front page must be the directory that exists.
    idx = blocks["index.html"]
    tree = next(b for b in idx if b.lstrip().startswith("changelog-tools/"))
    documented = parse_tree(tree)
    missing = [p for p in documented if not os.path.exists(os.path.join(PLUGIN, *p.split("/")))]
    check("every path in the index.html tree exists in example/changelog-tools",
          not missing, str(missing))
    real = {os.path.relpath(os.path.join(b, f), PLUGIN).replace("\\", "/")
            for b, _d, fs in os.walk(PLUGIN) for f in fs
            if "__pycache__" not in b}
    check("the tree names every file that exists — nothing is undocumented",
          real <= set(documented), str(sorted(real - set(documented))))

    # 8. The sample loader output on the front page must match the real output.
    sample = json.loads(strip_jsonc(next(b for b in idx if '"reports"' in b)))
    proc = subprocess.run([sys.executable, "loader.py", "../changelog-tools"], cwd=CLIENT,
                          capture_output=True, text=True, encoding="utf-8")
    live = json.loads(proc.stdout)
    check("the sample output names the plugin that the loader reports",
          sample["name"] == live["name"])
    check("the sample output lists the skill that the loader reports",
          [s["name"] for s in sample["skills"]] == [s["name"] for s in live["skills"]])
    check("the sample output lists the servers that the loader reports",
          {k: v["type"] for k, v in sample["servers"].items()}
          == {k: v["type"] for k, v in live["servers"].items()})
    check("the sample report line is the line the loader prints",
          sample["reports"] == live["reports"], str(sample["reports"]))

    # 7. The schemas in reference.html must accept the real files.
    ref = blocks["reference.html"]
    schemas = [json.loads(strip_jsonc(b)) for b in ref if '"$id"' in b or '"properties"' in b]
    check("reference.html prints two JSON Schemas", len(schemas) == 2, str(len(schemas)))
    for schema, real, label in zip(schemas, [real_manifest, real_mcp], ["plugin.json", "mcp.json"]):
        req = schema.get("required", [])
        check(f"the {label} schema lists required keys that the real file has",
              all(k in real for k in req), f"required={req}")
        props = schema.get("properties", {})
        check(f"every key of the real {label} appears in its schema",
              all(k in props for k in real), str([k for k in real if k not in props]))


def main():
    start = time.time()
    part_a()
    part_b()
    print(f"\n=== {len(PASS)} passed, {len(FAIL)} failed in {time.time() - start:.1f}s ===")
    for f in FAIL:
        print(f"  FAILED: {f}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
