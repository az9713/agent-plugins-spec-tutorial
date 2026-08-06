---
name: changelog-entry
description: Write a Keep a Changelog entry from a list of merged pull requests. Use when the user asks for a changelog, a release note, or a version summary.
---

# Changelog entry

Write one changelog entry for one version.

## Procedure

1. Read `references/format.md` for the required section order.
2. Group each change into one section: Added, Changed, Deprecated, Removed, Fixed, Security.
3. Write one line for each change. Start each line with a verb.
4. Add the version number and the release date in the format `## [1.2.0] - 2026-08-06`.
5. Run `scripts/check_entry.py <file>` to verify the section order.

## Rules

- Write for the user of the software, not for the developer.
- Name the user-visible effect. Do not name the internal function.
- Keep a pull request number at the end of the line, for example `(#412)`.
