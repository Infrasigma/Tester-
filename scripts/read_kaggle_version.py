#!/usr/bin/env python3
"""Parse the explicit current_version_number output supported by Kaggle CLI."""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path


def find_version(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit() and int(stripped) > 0:
            return int(stripped)
        try:
            return find_version(json.loads(stripped))
        except (ValueError, TypeError):
            match = re.search(r"(?i)current[_A-Za-z]*version(?:_number|Number)?[\"']?\s*[:=]\s*[\"']?(\d+)", stripped)
            return int(match.group(1)) if match else None
    if isinstance(value, dict):
        for key in ("current_version_number", "currentVersionNumber", "version_number", "versionNumber"):
            if key in value:
                found = find_version(value[key])
                if found is not None:
                    return found
        for child in value.values():
            found = find_version(child)
            if found is not None:
                return found
    if isinstance(value, list):
        for child in value:
            found = find_version(child)
            if found is not None:
                return found
    return None


def main():
    if len(sys.argv) != 2:
        print("VERSION_PARSE_FAILED", file=sys.stderr)
        return 2
    try:
        raw = Path(sys.argv[1]).read_text(encoding="utf-8")
        found = find_version(raw)
    except OSError:
        found = None
    if found is None:
        print("VERSION_PARSE_FAILED", file=sys.stderr)
        return 2
    print(found)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
