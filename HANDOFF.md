# HANDOFF — resume point for agent-plugins-spec-tutorial

**Read this first each new session.** This file is the live "what to do next".
`README.md` describes the project itself. Do not re-derive what the files already say — open them.

Repo: https://github.com/az9713/agent-plugins-spec-tutorial (public)
Site: https://az9713.github.io/agent-plugins-spec-tutorial/ (**not live yet — see Next task**)

## Current state (as of 2026-08-06, commit `5c5f31c`)

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

## Next task

**Deploy GitHub Pages, then verify the 4 screenshot links no longer 404.**

The site is blocked by a GitHub-side outage, not by this repo:

- GitHub status at 19:42 UTC on 2026-08-06: `Actions = major_outage`, `Pages = major_outage`.
  Incident "Incident with Actions" opened 2026-08-06T15:22:49Z.
- Three deploy runs failed the same way: `The job was not acquired by Runner of type hosted`.
  The `build` job succeeded each time and produced the `github-pages` artifact; only `deploy` never
  got a machine. Run 31126763438 may still be stuck in `waiting` and holds the `pages`
  concurrency group.
- Not a billing or settings problem: `actions/permissions` is `enabled: true, allowed_actions: all`,
  and other repos on this account (`agent-workflows`, `gpu-bio-lab`) had successful runs hours earlier.

Steps when Actions and Pages both read `operational` at https://www.githubstatus.com:

1. Cancel any run stuck in `waiting`:
   `gh run list -R az9713/agent-plugins-spec-tutorial --status waiting --json databaseId --jq '.[].databaseId'`
   then `gh run cancel <id> -R az9713/agent-plugins-spec-tutorial`
2. `gh workflow run pages.yml -R az9713/agent-plugins-spec-tutorial`
3. Wait for the run, then verify — **check the link destinations, not only the assets**:
   ```
   for u in "" plugin-authors.html client-implementers.html reference.html assets/screenshots/index.jpg; do
     curl -s -o /dev/null -w "$u %{http_code}\n" "https://az9713.github.io/agent-plugins-spec-tutorial/$u"
   done
   ```
   All five must return 200. No file change is needed — the README links already point at the right URLs.

No source edit is pending. The only open item is the deploy.

## Where to read things

- `README.md` — what the project is, the page map, how to run both reference clients.
- `.github/workflows/pages.yml` — the Actions deploy (uploads the repo root, `actions/deploy-pages@v4`).
- `../agent-plugins-spec/spec/1.0.0.md` — the canonical specification, if that clone still exists.
  Otherwise: https://github.com/agentplugins/agent-plugins-spec

## Session-transient scratch (regenerate if needed)

- `<scratchpad>/pages-watch.sh` — polls githubstatus.com every 5 minutes until Actions and Pages
  are both `operational`, cancels the stuck run, dispatches `pages.yml`, waits for it, then curls the
  5 URLs into `pages-watch.log`. Hard deadline 6 hours (01:42 UTC on 2026-08-07).
  It was running as background task `bqiddwddw`, which **does not survive a session clear** —
  assume it is dead and run the three steps under "Next task" by hand.
- `example/client/node_modules/` and `dist/` are gitignored. Rebuild with `npm install && npm test`.
- `example/.plugin-data/` is gitignored. Either reference client recreates it.

## How to work here

- Verify by observing the effect, not by a clean exit code: run the self-check, curl the URL, take
  the screenshot. A tool that exits 0 is not evidence.
- Check what a link actually opens before calling the work done.
- Every rule in the tutorial cites its specification section, for example `§7.2.1`. Keep that
  discipline when editing — a claim without a section is unverifiable.
