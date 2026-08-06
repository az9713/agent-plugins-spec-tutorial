#!/usr/bin/env node
/**
 * Reference Agent Plugins v1.0.0 client loader — TypeScript.
 *
 * The loader reads a plugin directory. It returns the discovered skills and the MCP
 * server launch plans. It applies the failure boundaries of the specification: a fault
 * in one component never removes an independent component.
 *
 * Build and run the self-check:
 *     npm install
 *     npm test
 *
 * Load the example plugin:
 *     npm run build && node dist/loader.js ../changelog-tools
 *
 * Section numbers refer to agent-plugins-spec/spec/1.0.0.md.
 */
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";

export const PLUGIN_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json";
export const MCP_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json";

/** The ten permitted top-level manifest keys and their JSON types (§5.2). */
const MANIFEST_FIELDS: Record<string, "string" | "object" | "array"> = {
  $schema: "string", name: "string", version: "string", description: "string",
  author: "object", homepage: "string", repository: "string", license: "string",
  keywords: "array", extensions: "object",
};
const AUTHOR_FIELDS = new Set(["name", "email", "url"]);

/** All four name constraints of §5.5 in one pattern. */
const NAME_RE = /^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$/;
/** The only two placeholders that expand (§9.2). */
const PLACEHOLDER_RE = /\$\{PLUGIN_ROOT\}|\$\{PLUGIN_DATA\}/g;
/** The three legal cwd forms (§7.2.1). */
const CWD_RE = /^(?:\.\/|\$\{PLUGIN_ROOT\}(?:\/|$)|\$\{PLUGIN_DATA\}(?:\/|$))/;
const LOOPBACK_RE = /^(?:localhost|127(?:\.\d+){3}|\[::1\])$/i;

/** A manifest violation that rejects the whole plugin (§5.3, §11.3). */
export class Fatal extends Error {}

export interface Skill { name: string; path: string }
export type ServerPlan =
  | { type: "stdio"; command: string; args: string[]; env: Record<string, string>; cwd: string }
  | { type: "streamable-http" | "sse"; url: string; headers: Record<string, string> };
export interface LoadedPlugin {
  name: string;
  manifest: Record<string, unknown>;
  skills: Skill[];
  servers: Record<string, ServerPlan>;
  extensions: Record<string, unknown>;
  reports: string[];
}
type Report = (message: string) => void;

// --- shared helpers ---------------------------------------------------------

/** Return true when p stays inside root after symlink resolution (§4.1). */
export function contained(p: string, root: string): boolean {
  const real = (x: string) => {
    try { return fs.realpathSync(x); } catch { return path.resolve(x); }
  };
  const rp = real(p);
  const rr = real(root);
  return rp === rr || rp.startsWith(rr + path.sep);
}

/**
 * Replace ${PLUGIN_ROOT} and ${PLUGIN_DATA} in ONE pass (§9.2).
 * String.replace with a function never rescans the inserted text. Two chained
 * replace calls would rescan, and a plugin could then inject a placeholder.
 */
export function expand(value: string, pluginRoot: string, pluginData: string): string {
  const table: Record<string, string> = {
    "${PLUGIN_ROOT}": pluginRoot,
    "${PLUGIN_DATA}": pluginData,
  };
  return value.replace(PLACEHOLDER_RE, (m) => table[m]!);
}

/** Resolve a plugin-relative './x' path against root. Return null when it escapes (§4.1). */
export function resolveRel(value: string, root: string): string | null {
  if (!value.startsWith("./")) return null;
  const p = path.join(root, value.slice(2));
  return contained(p, root) ? p : null;
}

function jsonKind(v: unknown): string {
  if (Array.isArray(v)) return "array";
  if (v === null) return "null";
  return typeof v;
}

// --- step 2: the manifest ---------------------------------------------------

/** Read and validate plugin.json. Throw Fatal to reject the plugin (§5). */
export function loadManifest(root: string, report: Report): Record<string, unknown> {
  const file = path.join(root, "plugin.json");
  if (!contained(file, root)) throw new Fatal("plugin.json resolves outside the plugin root");

  let raw: string;
  try {
    raw = fs.readFileSync(file, "utf8");
  } catch {
    throw new Fatal("plugin.json is missing");
  }
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch (e) {
    throw new Fatal(`plugin.json is not valid JSON: ${(e as Error).message}`);
  }
  if (jsonKind(data) !== "object") throw new Fatal("plugin.json is not a JSON object");
  const m = data as Record<string, unknown>;

  // Non-fatal case 1: an unknown top-level key (§5.2).
  for (const key of Object.keys(m)) {
    if (!(key in MANIFEST_FIELDS)) {
      report(`unknown manifest field ignored: ${key}`);
      delete m[key];
    }
  }

  if (m["$schema"] !== PLUGIN_SCHEMA) {
    throw new Fatal(`unsupported $schema: ${JSON.stringify(m["$schema"])}`);
  }
  const name = m["name"];
  if (typeof name !== "string" || name.length < 1 || name.length > 64 || !NAME_RE.test(name)) {
    throw new Fatal(`invalid name: ${JSON.stringify(name)}`);
  }

  for (const [key, kind] of Object.entries(MANIFEST_FIELDS)) {
    if (!(key in m)) continue;
    if (jsonKind(m[key]) === kind) continue;
    // Non-fatal case 2: extensions is not an object (§8.1).
    if (key === "extensions") {
      report("extensions is not an object; field ignored");
      m["extensions"] = {};
      continue;
    }
    throw new Fatal(`field ${key} has the wrong type`);
  }

  const keywords = m["keywords"];
  if (Array.isArray(keywords) && !keywords.every((k) => typeof k === "string")) {
    throw new Fatal("keywords must contain strings only");
  }
  const author = m["author"];
  if (jsonKind(author) === "object") {
    for (const [key, val] of Object.entries(author as Record<string, unknown>)) {
      if (!AUTHOR_FIELDS.has(key) || typeof val !== "string") {
        throw new Fatal(`invalid author field: ${key}`);
      }
    }
  }
  const extensions = (m["extensions"] ?? {}) as Record<string, unknown>;
  for (const [ns, val] of Object.entries(extensions)) {
    if (jsonKind(val) !== "object") throw new Fatal(`extensions.${ns} is not an object`);
  }
  return m;
}

// --- step 4a: skills --------------------------------------------------------

/** Return the skill directories under skills/ (§6.1, §7.1). */
export function discoverSkills(root: string, report: Report): Skill[] {
  const base = path.join(root, "skills");
  if (!fs.existsSync(base)) return [];                    // missing is not an error (§6.2)
  if (!fs.statSync(base).isDirectory()) {
    report("skills exists but is not a directory; skills disabled");
    return [];                                            // wrong kind: type invalid (§6.2)
  }
  const skills: Skill[] = [];
  for (const entry of fs.readdirSync(base).sort()) {      // immediate children only (§7.1)
    const skillMd = path.join(base, entry, "SKILL.md");
    if (!fs.existsSync(skillMd) || !fs.statSync(skillMd).isFile()) continue;
    if (!contained(skillMd, root)) {
      report(`skill ${entry} escapes the plugin root; skipped`);
      continue;
    }
    skills.push({ name: entry, path: skillMd });
  }
  return skills;
}

// --- step 4b: MCP servers ---------------------------------------------------

/** Return a launch plan, or throw for an invalid entry (§7.2). */
export function validateServer(entry: unknown, root: string, pluginData: string): ServerPlan {
  if (jsonKind(entry) !== "object" || !("type" in (entry as object))) {
    throw new Error("server entry has no type");
  }
  const e = entry as Record<string, unknown>;
  const kind = e["type"];

  if (kind === "stdio") {
    const allowed = new Set(["type", "command", "args", "env", "cwd"]);
    const extra = Object.keys(e).filter((k) => !allowed.has(k));
    if (extra.length) throw new Error(`unknown stdio fields: ${extra.sort().join(", ")}`);

    const rawCommand = e["command"];
    if (typeof rawCommand !== "string" || rawCommand.length === 0) {
      throw new Error("command is missing");
    }
    let command: string = rawCommand;
    if (command.startsWith("./")) {
      const resolved = resolveRel(command, root);
      if (resolved === null) throw new Error("command escapes the plugin root");
      command = resolved;
    } else if (command.includes("/") || command.includes("\\")) {
      throw new Error("command must be a bare name or a ./ path");
    }

    const args = e["args"] ?? [];
    if (!Array.isArray(args) || !args.every((a) => typeof a === "string")) {
      throw new Error("args must be a list of strings");
    }
    const env = e["env"] ?? {};
    if (jsonKind(env) !== "object" ||
        !Object.values(env as object).every((v) => typeof v === "string")) {
      throw new Error("env must be an object of strings");
    }
    const envObj = env as Record<string, string>;
    if ("PLUGIN_ROOT" in envObj || "PLUGIN_DATA" in envObj) {
      throw new Error("env must not set PLUGIN_ROOT or PLUGIN_DATA");        // §9.2
    }

    const cwd = e["cwd"];
    let cwdPath: string;
    if (cwd === undefined) {
      cwdPath = root;                                                        // default (§7.2.1)
    } else {
      if (typeof cwd !== "string" || !CWD_RE.test(cwd)) {
        throw new Error(`invalid cwd form: ${JSON.stringify(cwd)}`);
      }
      const source = cwd.startsWith("./") ? path.join(root, cwd.slice(2)) : cwd;
      cwdPath = path.normalize(expand(source, root, pluginData));
      const base = cwd.startsWith("${PLUGIN_DATA}") ? pluginData : root;
      if (!contained(cwdPath, base)) throw new Error("cwd escapes its base directory");
    }

    // The client sets the reserved variables LAST (§9.1).
    const finalEnv: Record<string, string> = {};
    for (const [k, v] of Object.entries(envObj)) finalEnv[k] = expand(v, root, pluginData);
    finalEnv["PLUGIN_ROOT"] = root;
    finalEnv["PLUGIN_DATA"] = pluginData;

    return {
      type: "stdio",
      command,
      args: (args as string[]).map((a) => expand(a, root, pluginData)),
      env: finalEnv,
      cwd: cwdPath,
    };
  }

  if (kind === "streamable-http" || kind === "sse") {
    const allowed = new Set(["type", "url", "headers"]);
    const extra = Object.keys(e).filter((k) => !allowed.has(k));
    if (extra.length) throw new Error(`unknown ${kind} fields: ${extra.sort().join(", ")}`);

    const url = e["url"];
    if (typeof url !== "string") throw new Error("url is missing");
    const m = /^(https?):\/\/([^/?#]+)(?:[/?#]|$)/i.exec(url);
    if (!m) throw new Error("url must be an absolute http or https URL");
    const scheme = m[1]!.toLowerCase();
    const host = m[2]!;
    if (host.includes("@")) throw new Error("url must not contain user information");
    if (url.includes("#")) throw new Error("url must not contain a fragment");
    const hostname = host.startsWith("[") ? host.slice(0, host.indexOf("]") + 1)
                                          : host.split(":")[0]!;
    if (scheme === "http" && !LOOPBACK_RE.test(hostname)) {
      throw new Error("http is allowed for a loopback host only");
    }

    const headers = e["headers"] ?? {};
    if (jsonKind(headers) !== "object" ||
        !Object.values(headers as object).every((v) => typeof v === "string")) {
      throw new Error("headers must be an object of strings");
    }
    const lowered = Object.keys(headers as object).map((k) => k.toLowerCase());
    if (new Set(lowered).size !== lowered.length) {
      throw new Error("duplicate header name under different casing");
    }
    // No expansion in url or headers (§7.2.1).
    return { type: kind, url, headers: { ...(headers as Record<string, string>) } };
  }

  throw new Error(`unknown transport: ${JSON.stringify(kind)}`);
}

/** Return the valid server plans from mcp.json (§7.2.2). */
export function loadMcp(
  root: string,
  manifestSchema: string,
  pluginData: string,
  report: Report,
  transports: readonly string[] = ["stdio", "streamable-http"],
): Record<string, ServerPlan> {
  const file = path.join(root, "mcp.json");
  if (!fs.existsSync(file)) return {};                    // missing is not an error (§6.2)
  if (!fs.statSync(file).isFile()) {
    report("mcp.json exists but is not a regular file; MCP disabled");
    return {};
  }
  let data: unknown;
  try {
    data = JSON.parse(fs.readFileSync(file, "utf8"));
  } catch (e) {
    report(`mcp.json is not valid JSON: ${(e as Error).message}; MCP disabled`);
    return {};
  }
  if (jsonKind(data) !== "object") {
    report("mcp.json is not a JSON object; MCP disabled");
    return {};
  }
  const d = data as Record<string, unknown>;
  const keys = Object.keys(d).sort().join(",");
  if (keys !== "$schema,mcpServers") {
    report("mcp.json has wrong top-level fields; MCP disabled");
    return {};
  }
  if (d["$schema"] !== MCP_SCHEMA) {
    report("mcp.json targets an unsupported version; MCP disabled");
    return {};
  }
  const versionOf = (id: string) => id.split("/").slice(-2)[0];
  if (versionOf(d["$schema"] as string) !== versionOf(manifestSchema)) {
    report("mcp.json version differs from plugin.json; MCP disabled");      // §10.1
    return {};
  }
  if (jsonKind(d["mcpServers"]) !== "object") {
    report("mcpServers is not an object; MCP disabled");
    return {};
  }

  const plans: Record<string, ServerPlan> = {};
  for (const [name, entry] of Object.entries(d["mcpServers"] as Record<string, unknown>)) {
    let plan: ServerPlan;
    try {
      plan = validateServer(entry, root, pluginData);
    } catch (err) {
      report(`server ${name} skipped: ${(err as Error).message}`);          // §7.2.2 rule 3
      continue;
    }
    if (!transports.includes(plan.type)) {
      report(`server ${name} skipped: transport ${plan.type} is unsupported`);
      continue;                                                             // §7.2.2 rule 4
    }
    plans[name] = plan;
  }
  return plans;
}

/** Load one plugin directory. Throw Fatal to reject the plugin (§11.1). */
export function loadPlugin(
  rootIn: string,
  pluginDataIn?: string,
  transports: readonly string[] = ["stdio", "streamable-http"],
): LoadedPlugin {
  const root = fs.realpathSync(path.resolve(rootIn));
  // PLUGIN_DATA lives OUTSIDE the package. An update replaces the package contents,
  // and the data directory must survive that update (§9.1).
  const defaultData = path.join(path.dirname(root), ".plugin-data", path.basename(root));
  const wanted = path.resolve(pluginDataIn ?? defaultData);
  fs.mkdirSync(wanted, { recursive: true });                                // §9.1
  const pluginData = fs.realpathSync(wanted);

  const reports: string[] = [];
  const report: Report = (msg) => reports.push(msg);
  const manifest = loadManifest(root, report);
  return {
    name: manifest["name"] as string,
    manifest,
    skills: discoverSkills(root, report),
    servers: loadMcp(root, manifest["$schema"] as string, pluginData, report, transports),
    extensions: (manifest["extensions"] ?? {}) as Record<string, unknown>,
    reports,
  };
}

// --- self-check -------------------------------------------------------------

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(`self-check failed: ${message}`);
}

export function demo(): void {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "apt-"));
  const write = (base: string, rel: string, text: string) => {
    const p = path.join(base, rel);
    fs.mkdirSync(path.dirname(p), { recursive: true });
    fs.writeFileSync(p, text, "utf8");
  };
  try {
    const root = path.join(tmp, "p");
    write(root, "plugin.json", JSON.stringify({
      $schema: PLUGIN_SCHEMA, name: "demo.plugin", nope: 1,
      extensions: { "com.example.client": { a: 1 } },
    }));
    write(root, "skills/one/SKILL.md", "---\nname: one\ndescription: d\n---\n");
    write(root, "skills/two/README.md", "not a skill");
    write(root, "skills/one/nested/SKILL.md", "must not be discovered");
    write(root, "mcp.json", JSON.stringify({
      $schema: MCP_SCHEMA,
      mcpServers: {
        ok: {
          type: "stdio", command: "node", args: ["${PLUGIN_ROOT}/bin/x.js"],
          env: { D: "${PLUGIN_DATA}/d" }, cwd: "${PLUGIN_DATA}",
        },
        escape: { type: "stdio", command: "../evil" },
        reserved: { type: "stdio", command: "x", env: { PLUGIN_ROOT: "/tmp" } },
        plain_http: { type: "streamable-http", url: "http://example.com/mcp" },
        local_http: { type: "streamable-http", url: "http://localhost:8080/mcp" },
        legacy: { type: "sse", url: "https://legacy.example.com/sse" },
        bogus: { type: "websocket", url: "wss://x" },
      },
    }));

    const dataDir = path.join(tmp, "data");
    const p = loadPlugin(root, dataDir);
    const realRoot = fs.realpathSync(root);
    const realData = fs.realpathSync(dataDir);

    assert(p.name === "demo.plugin", "name");
    assert(!("nope" in p.manifest), "the unknown field must be dropped");
    assert(p.reports.some((r) => r.includes("unknown manifest field")), "unknown field report");
    assert(JSON.stringify(p.skills.map((s) => s.name)) === '["one"]', "one-level discovery");
    assert(Object.keys(p.servers).sort().join(",") === "local_http,ok",
      `servers: ${Object.keys(p.servers)}`);

    const ok = p.servers["ok"] as Extract<ServerPlan, { type: "stdio" }>;
    assert(ok.args[0] === `${realRoot}/bin/x.js`, `args: ${ok.args[0]}`);
    assert(ok.env["PLUGIN_ROOT"] === realRoot, "PLUGIN_ROOT is set by the client");
    assert(ok.env["D"]!.startsWith(realData), "PLUGIN_DATA expands in an env value");
    assert(ok.cwd === realData, `cwd: ${ok.cwd}`);
    assert(p.reports.some((r) => r.includes("legacy") && r.includes("unsupported")), "sse report");

    // A single non-recursive expansion pass (§9.2).
    assert(expand("${PLUGIN_ROOT}", "${PLUGIN_DATA}", "/d") === "${PLUGIN_DATA}", "no rescan");
    assert(expand("a${PLUGIN_ROOT}b${PLUGIN_DATA}c", "/r", "/d") === "a/rb/dc", "both expand");
    assert(expand("${OTHER}", "/r", "/d") === "${OTHER}", "unknown stays literal");

    // Fatal manifest cases (§5.2, §5.3, §5.5).
    const badManifests: Record<string, unknown>[] = [
      { name: "x" },
      { $schema: PLUGIN_SCHEMA },
      { $schema: PLUGIN_SCHEMA, name: "Bad-Name" },
      { $schema: PLUGIN_SCHEMA, name: "has--double" },
      { $schema: PLUGIN_SCHEMA, name: "-lead" },
      { $schema: "https://example.com/other.json", name: "x" },
      { $schema: PLUGIN_SCHEMA, name: "x", keywords: "no" },
      { $schema: PLUGIN_SCHEMA, name: "x", author: { nick: "n" } },
    ];
    for (const bad of badManifests) {
      write(root, "plugin.json", JSON.stringify(bad));
      let rejected = false;
      try { loadPlugin(root, dataDir); } catch (e) { rejected = e instanceof Fatal; }
      assert(rejected, `expected rejection: ${JSON.stringify(bad)}`);
    }

    // A non-object extensions field is NOT fatal (§8.1).
    write(root, "plugin.json", JSON.stringify(
      { $schema: PLUGIN_SCHEMA, name: "x", extensions: "no" }));
    const p2 = loadPlugin(root, dataDir);
    assert(Object.keys(p2.extensions).length === 0, "extensions cleared");
    assert(p2.reports.some((r) => r.includes("extensions is not an object")), "extensions report");

    console.log("loader self-check passed");
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true });
  }
}

if (require.main === module) {
  const target = process.argv[2];
  if (target) {
    console.log(JSON.stringify(loadPlugin(target), null, 2));
  } else {
    demo();
  }
}
