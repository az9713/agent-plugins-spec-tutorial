# HANDOFF — resume point for agent-plugins-spec-tutorial

**Read this first each new session.** This file is the live "what to do next".
`README.md` describes the project itself. Do not re-derive what the files already say — open them.

Repo: https://github.com/az9713/agent-plugins-spec-tutorial (public)
Site: https://az9713.github.io/agent-plugins-spec-tutorial/ (**live**)

## Current state (as of 2026-08-06, commit `6b1af03`)

Everything is committed and pushed to `main`. Local `HEAD` matches `origin/main`. The working tree is clean.

Done and verified:

- **4 HTML tutorial pages**, self-contained, no CDN: `index.html`, `plugin-authors.html`,
  `client-implementers.html`, `reference.html`. Shared `assets/style.css` and `assets/tutorial.js`
  (theme toggle, syntax highlighting, copy buttons, TOC scrollspy). Verified in a real browser in
  both themes: 0 px horizontal overflow, 149 highlight tokens in the JSONC block, 0 false comments
  inside URL strings, all internal links resolve. Landed in `c1e2034`.
- **Worked example plugin** `example/changelog-tools/`: all 10 manifest keys, 3 MCP transports,
  a skill with `references/` and `scripts/`, a working stdio MCP server in `bin/notes_server.py`,
  and a `com.example.client/` extension directory.
- **Two reference clients**, standard library only, same behavior:
  `example/client/loader.ts` (357 lines, strict TS) and `example/client/loader.py`.
  Both self-checks pass. Both produce the same launch plan for the example, including the report
  line `server legacy-feed skipped: transport sse is unsupported`.
- **4 light-theme screenshots** in `assets/screenshots/`, wired into `README.md` as a clickable
  2x2 grid. The images serve correctly (HTTP 200 from `raw.githubusercontent.com`). Landed in `b9ccf92`.

- **The site is deployed and live.** Run 31129025363 (`Deploy tutorial to GitHub Pages`) finished
  `success` at about 22:30 UTC on 2026-08-06, after the earlier GitHub Actions outage recovered.
  The three failed runs and the stuck `waiting` run 31126763438 were the outage, not this repo;
  31126763438 was cancelled to free the `pages` concurrency group before the new dispatch.
- **All 10 live URLs return HTTP 200**: the 4 pages, the 4 screenshot JPEGs, `assets/style.css`,
  and `assets/tutorial.js`. The served `index.html` is 11222 bytes with the correct `<title>`.
  Every destination behind the README screenshot grid is one of those 4 verified page URLs.

## Next task

**Nothing is pending.** The tutorial is written, committed, deployed, and verified.

Possible follow-ups, in the order of value. None is started:

1. Track the specification. If `agent-plugins-spec` publishes a version after 1.0.0, compare it
   against the field tables in `reference.html` and the rules in the other 3 pages.
2. Add a link check to CI. `.github/workflows/pages.yml` deploys but does not test.
3. Add dark-theme screenshots. `assets/screenshots/` holds light-theme images only.

Re-deploy at any time with `gh workflow run pages.yml -R az9713/agent-plugins-spec-tutorial`.
After a deploy, verify with:

```
B=https://az9713.github.io/agent-plugins-spec-tutorial
for u in "" plugin-authors.html client-implementers.html reference.html \
         assets/screenshots/index.jpg assets/screenshots/plugin-authors.jpg \
         assets/screenshots/client-implementers.jpg assets/screenshots/reference.jpg; do
  curl -sL -o /dev/null -w "$u %{http_code}\n" "$B/$u"
done
```

All 8 must return 200.

## Where to read things

- `README.md` — what the project is, the page map, how to run both reference clients.
- `.github/workflows/pages.yml` — the Actions deploy (uploads the repo root, `actions/deploy-pages@v4`).
- `../agent-plugins-spec/spec/1.0.0.md` — the canonical specification, if that clone still exists.
  Otherwise: https://github.com/agentplugins/agent-plugins-spec

## Session-transient scratch (regenerate if needed)

- `<scratchpad>/pages-watch.sh` — the outage poller. It is obsolete: the deploy is done. Delete it.
- `example/client/node_modules/` and `dist/` are gitignored. Rebuild with `npm install && npm test`.
- `example/.plugin-data/` is gitignored. Either reference client recreates it.

## How to work here

- Verify by observing the effect, not by a clean exit code: run the self-check, curl the URL, take
  the screenshot. A tool that exits 0 is not evidence.
- Check what a link actually opens before calling the work done.
- Every rule in the tutorial cites its specification section, for example `§7.2.1`. Keep that
  discipline when editing — a claim without a section is unverifiable.
