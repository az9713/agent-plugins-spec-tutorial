#!/usr/bin/env python3
"""Check that a changelog entry uses the required section order."""
import re
import sys

ORDER = ["Added", "Changed", "Deprecated", "Removed", "Fixed", "Security"]


def check(text):
    """Return a list of error strings. An empty list means the entry is valid."""
    errors = []
    if not re.search(r"^## \[\d+\.\d+\.\d+\] - \d{4}-\d{2}-\d{2}$", text, re.M):
        errors.append("missing or malformed version heading")
    found = re.findall(r"^### (\w+)$", text, re.M)
    unknown = [s for s in found if s not in ORDER]
    if unknown:
        errors.append(f"unknown sections: {unknown}")
    ranks = [ORDER.index(s) for s in found if s in ORDER]
    if ranks != sorted(ranks):
        errors.append("sections are out of order")
    return errors


def demo():
    good = "## [1.2.0] - 2026-08-06\n\n### Added\n- x\n\n### Fixed\n- y\n"
    bad = "## [1.2.0] - 2026-08-06\n\n### Fixed\n- y\n\n### Added\n- x\n"
    assert check(good) == [], check(good)
    assert "sections are out of order" in check(bad)
    assert "missing or malformed version heading" in check("### Added\n- x\n")
    print("check_entry self-check passed")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        demo()
    else:
        errs = check(open(sys.argv[1], encoding="utf-8").read())
        for e in errs:
            print(e)
        sys.exit(1 if errs else 0)
