# HANDOFF — resume point for agent-plugins-spec-tutorial

**Read this first each new session.** This file is the live "what to do next".
`README.md` describes the project itself. Do not re-derive what the files already say — open them.

Repo: https://github.com/az9713/agent-plugins-spec-tutorial (public)
Site: https://az9713.github.io/agent-plugins-spec-tutorial/ (**live**)

## Current state (as of 2026-08-07)

The invariant to restore after any change: local `HEAD` = `origin/main` = the newest deployment sha,
and a clean working tree. Do not trust this file's word for it — run the two checks at the end of
the next section. `HEAD` was last confirmed equal to the deployed commit at `f0cbb5f`, delivered by
run 31138409010, with all 14 URLs at 200 and each of the 6 screenshots serving a byte count equal to
its git blob.

Done and verified:

- **`index.html` links every other page twice**: from the nav, and from the body — three cards for
  the tutorial pages, then a second `.cards` group for `implementation.html` and `e2e-tests.html`,
  plus a row each in the "How to read this tutorial" table. Keep the two card groups separate.
  The grid is `repeat(auto-fit, minmax(250px, 1fr))` (`assets/style.css:374`), so a single group of
  5 cards wraps 4 + 1 and looks broken.
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
- **6 light-theme screenshots** in `assets/screenshots/`, one per page, wired into `README.md` as a
  clickable 3x2 grid. All 6 are 1568x709 JPEG. The original 4 landed in `b9ccf92` but went stale when
  `87d36f2` added 2 pages to every nav, so all 6 were re-shot together against the live site.
  Recipe, if they need shooting again: chrome-devtools `new_page` with an isolated context,
  `emulate` `colorScheme: light` and viewport `1568x709x1`, **then reload** — the theme toggle paints
  its label once at load (`assets/tutorial.js:17`), so a page loaded before the emulation shows
  "Light" on a light page. Confirm with `evaluate_script` that the label reads `Dark` and
  `prefersDark` is `false` before capturing. `take_screenshot` writes `.jpeg`; rename to `.jpg`.
- **Every link in `README.md` is absolute.** Relative links such as `](implementation.html)` open the
  raw HTML source on github.com instead of the page. Only the 6 screenshot images stay repo-relative,
  which is required for them to render.

- **The site is deployed and live.** The newest run is 31134457291 (`workflow_dispatch`), which
  finished `success` at 00:23 UTC on 2026-08-07 for commit `6d899ba`. Earlier failed runs and the
  stuck `waiting` run 31126763438 were the GitHub Actions outage, not this repo.
- **The live URL check covers 14 things**: the 6 pages, the 6 screenshot JPEGs, `assets/style.css`,
  and `assets/tutorial.js`. All 14 returned 200 as of the last verified deploy. The 2 newest JPEGs,
  `implementation.jpg` and `e2e-tests.jpg`, only serve once their commit is pushed and deployed —
  re-run the loop below after any push. Every destination behind the README screenshot grid is one
  of the 6 page URLs. To confirm the newest content is live and not a cached older deploy, compare
  the served byte count with the git blob, which must be equal:

  ```bash
  echo "served=$(curl -sL https://az9713.github.io/agent-plugins-spec-tutorial/ | wc -c) \
        blob=$(git cat-file -s HEAD:index.html)"
  ```

  Do **not** compare against the file on disk. A Windows checkout uses CRLF, so `wc -c index.html`
  reports one extra byte per line — 247 more than the blob, at 247 lines. Compare the git blob size.
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
3. Add dark-theme screenshots. `assets/screenshots/` holds light-theme images only. All 6 pages now
   have one, so only the dark variant is missing.

Re-deploy at any time with `gh workflow run pages.yml -R az9713/agent-plugins-spec-tutorial`.
After a deploy, run these two checks in order. The second one is the important one.

```bash
# 1. The newest deployment must hold the newest commit. A green run is not proof.
echo "HEAD=$(git rev-parse --short HEAD) deployed=$(gh api \
  repos/az9713/agent-plugins-spec-tutorial/deployments --jq '.[0].sha[0:7]')"

# 2. All 14 URLs must return 200.
B=https://az9713.github.io/agent-plugins-spec-tutorial
for u in "" plugin-authors.html client-implementers.html reference.html \
         implementation.html e2e-tests.html \
         assets/screenshots/index.jpg assets/screenshots/plugin-authors.jpg \
         assets/screenshots/client-implementers.jpg assets/screenshots/reference.jpg \
         assets/screenshots/implementation.jpg assets/screenshots/e2e-tests.jpg \
         assets/style.css assets/tutorial.js; do
  curl -sL -o /dev/null -w "$u %{http_code}\n" "$B/$u"
done
```

## Where to read things

- `README.md` — what the project is, the page map, how to run both reference clients and `e2e.py`.
- `example/e2e.py` — the one command that proves the whole tutorial works. Run it after any edit
  to a page, to a manifest, or to a loader.
- `.github/workflows/pages.yml` — the Actions deploy (uploads the repo root, `actions/deploy-pages@v4`).
- `../agent-plugins-spec/spec/1.0.0.md` — the canonical specification, if that clone still exists.
  Otherwise: https://github.com/agentplugins/agent-plugins-spec

## Session-transient scratch (regenerate if needed)

- Nothing is pending in a scratchpad. The old `pages-watch.sh` outage poller is deleted and obsolete.
- `example/client/node_modules/` and `dist/` are gitignored. Rebuild with `npm install && npm test`.
- `example/.plugin-data/` is gitignored. Either reference client recreates it, and so does `e2e.py`.
- To capture the check list for a document, run
  `python example/e2e.py --quiet > out.txt` and read `out.txt`. Do not hand-copy the 59 labels.

## How to work here

- Verify by observing the effect, not by a clean exit code: run the self-check, curl the URL, take
  the screenshot. A tool that exits 0 is not evidence.
- Check what a link actually opens before calling the work done.
- Every rule in the tutorial cites its specification section, for example `§7.2.1`. Keep that
  discipline when editing — a claim without a section is unverifiable.
