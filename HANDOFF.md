# HANDOFF — resume point for agent-plugins-spec-tutorial

**Read this first each new session.** This file is the live "what to do next".
`README.md` describes the project itself. Do not re-derive what the files already say — open them.

Repo: https://github.com/az9713/agent-plugins-spec-tutorial (public)
Site: https://az9713.github.io/agent-plugins-spec-tutorial/ (**live**)

## Current state (as of 2026-08-06, commit `87d36f2`)

Everything is committed and pushed to `main`. Local `HEAD` matches `origin/main`. The working tree is clean.

Done and verified:

- **6 HTML pages.** 4 tutorial pages, self-contained, no CDN: `index.html`, `plugin-authors.html`,
  `client-implementers.html`, `reference.html` — plus `implementation.html` (what the code
  contains, and a measured verdict on tutorial-versus-code fidelity: 149 of 165 TypeScript lines are
  verbatim, and every block that claims to be a file is identical) and `e2e-tests.html` (all 59
  checks explained, the untested parts, and what the passes do and do not prove; landed in `87d36f2`).
  All 6 share `assets/style.css` and `assets/tutorial.js` (theme toggle, syntax highlighting, copy
  buttons, TOC scrollspy), and every nav lists all 6. The 4 tutorial pages were verified in a real
  browser in both themes: 0 px horizontal overflow, 149 highlight tokens in the JSONC block, 0 false
  comments inside URL strings (`c1e2034`). All 6 pages pass a well-formedness parse, and all internal
  links and anchors resolve — 0 broken.
- **Worked example plugin** `example/changelog-tools/`: all 10 manifest keys, 3 MCP transports,
  a skill with `references/` and `scripts/`, a working stdio MCP server in `bin/notes_server.py`,
  and a `com.example.client/` extension directory.
- **Two reference clients**, standard library only, same behavior:
  `example/client/loader.ts` (484 lines, strict TS) and `example/client/loader.py` (357 lines).
  Both self-checks pass. Both produce the same launch plan for the example, including the report
  line `server legacy-feed skipped: transport sse is unsupported`.
- **4 light-theme screenshots** in `assets/screenshots/`, wired into `README.md` as a clickable
  2x2 grid. The images serve correctly (HTTP 200 from `raw.githubusercontent.com`). Landed in `b9ccf92`.

- **The site is deployed and live.** Run 31129025363 (`Deploy tutorial to GitHub Pages`) finished
  `success` at about 22:30 UTC on 2026-08-06, after the earlier GitHub Actions outage recovered.
  The three failed runs and the stuck `waiting` run 31126763438 were the outage, not this repo;
  31126763438 was cancelled to free the `pages` concurrency group before the new dispatch.
- **All 12 live URLs return HTTP 200**: the 6 pages, the 4 screenshot JPEGs, `assets/style.css`,
  and `assets/tutorial.js`. Every destination behind the README screenshot grid is one of those
  4 verified page URLs. The served `index.html` is 11887 bytes and names `e2e.py` twice, which is
  how you confirm the newest content is live and not a cached older deploy.
- **`example/e2e.py` — the end-to-end demonstration. 59 checks, exit code 0.** Landed in `fe3acce`.
  Run it with `python example/e2e.py` (add `--quiet` to hide the MCP transcript). Part A loads the
  plugin with the reference client, launches `bin/notes_server.py` from the client's own launch
  plan, and speaks MCP to it. Part B compares every code block on the 4 HTML pages with the files
  in `example/`. A mutation test proved it fails when reality drifts: change `${PLUGIN_DATA}` to
  `${PLUGIN_ROOT}` in `mcp.json` and 4 checks turn red and the exit code becomes 1.
  **Part B scans the 4 tutorial pages only.** `implementation.html` and `e2e-tests.html` are outside
  it, on purpose — adding them changes the count that `e2e-tests.html` documents. To cover them
  later, add both names to `PAGES` in `example/e2e.py` and update the count on that page.

**Deploy trap, learned the hard way.** `pages.yml` also triggers `on: push`. Three pushes in a row
queued three runs, and the run that finished last deployed the *oldest* of the three commits. The
site then served stale content while every URL still returned 200. After a group of pushes, dispatch
`pages.yml` once by hand and confirm with `gh api repos/az9713/agent-plugins-spec-tutorial/deployments
--jq '.[0].sha'` that the newest deployment holds the newest commit.

## Next task

**Nothing is pending.** The tutorial is written, committed, deployed, demonstrated, and verified.

Possible follow-ups, in the order of value. None is started:

1. Track the specification. If `agent-plugins-spec` publishes a version after 1.0.0, compare it
   against the field tables in `reference.html` and the rules in the other 3 pages.
2. Run `example/e2e.py` in CI. It already exits non-zero on a failure, so a small workflow that
   calls it turns doc drift into a red build. `.github/workflows/pages.yml` deploys but does not test.
3. Add dark-theme screenshots. `assets/screenshots/` holds light-theme images only. There is also
   no screenshot for the 2 new pages.

Re-deploy at any time with `gh workflow run pages.yml -R az9713/agent-plugins-spec-tutorial`.
After a deploy, verify with:

```
B=https://az9713.github.io/agent-plugins-spec-tutorial
for u in "" plugin-authors.html client-implementers.html reference.html          implementation.html e2e-tests.html \
         assets/screenshots/index.jpg assets/screenshots/plugin-authors.jpg \
         assets/screenshots/client-implementers.jpg assets/screenshots/reference.jpg; do
  curl -sL -o /dev/null -w "$u %{http_code}\n" "$B/$u"
done
```

All 10 must return 200.

## Where to read things

- `README.md` — what the project is, the page map, how to run both reference clients and `e2e.py`.
- `example/e2e.py` — the one command that proves the whole tutorial works. Run it after any edit
  to a page, to a manifest, or to a loader.
- `.github/workflows/pages.yml` — the Actions deploy (uploads the repo root, `actions/deploy-pages@v4`).
- `../agent-plugins-spec/spec/1.0.0.md` — the canonical specification, if that clone still exists.
  Otherwise: https://github.com/agentplugins/agent-plugins-spec

## Session-transient scratch (regenerate if needed)

- `example/client/node_modules/` and `dist/` are gitignored. Rebuild with `npm install && npm test`.
- `example/.plugin-data/` is gitignored. Either reference client recreates it.

## How to work here

- Verify by observing the effect, not by a clean exit code: run the self-check, curl the URL, take
  the screenshot. A tool that exits 0 is not evidence.
- Check what a link actually opens before calling the work done.
- Every rule in the tutorial cites its specification section, for example `§7.2.1`. Keep that
  discipline when editing — a claim without a section is unverifiable.
