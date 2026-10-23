#!/usr/bin/env python3
"""Configure Kaggle CLI credentials on a GitHub-hosted runner without logging secrets."""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import sys


def main() -> int:
    raw = os.environ.get("KAGGLE_API_TOKEN", "").strip()
    if not raw:
        print("KAGGLE_AUTH_FAILED: missing repository secret", file=sys.stderr)
        return 2
    owner = os.environ.get("KAGGLE_USERNAME", os.environ.get("KAGGLE_OWNER", "memorican")).strip()
    home = Path.home()
    kaggle_dir = home / ".kaggle"
    kaggle_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    credentials_path = kaggle_dir / "kaggle.json"
    github_env = os.environ.get("GITHUB_ENV")

    def set_future_env(name: str, value: str) -> None:
        if github_env:
            with open(github_env, "a", encoding="utf-8") as stream:
                stream.write(f"{name}={value}\n")

    # Current Kaggle personal API tokens use the bearer-token environment variable.
    # Legacy CLI keys use ~/.kaggle/kaggle.json. Both secret encodings are accepted.
    try:
        decoded = json.loads(raw) if raw.startswith("{") else None
    except json.JSONDecodeError:
        decoded = None
    if isinstance(decoded, dict) and isinstance(decoded.get("username"), str) and isinstance(decoded.get("key"), str):
        credentials = {"username": decoded["username"], "key": decoded["key"]}
        credentials_path.write_text(json.dumps(credentials), encoding="utf-8")
        credentials_path.chmod(0o600)
        set_future_env("KAGGLE_API_TOKEN", "")
        set_future_env("KAGGLE_AUTH_MODE", "legacy-json")
    elif isinstance(decoded, dict) and any(isinstance(decoded.get(k), str) for k in ("token", "access_token", "apiToken")):
        token_value = next(decoded[k] for k in ("token", "access_token", "apiToken") if isinstance(decoded.get(k), str))
        if not token_value.strip():
            print("KAGGLE_AUTH_FAILED: empty token field", file=sys.stderr)
            return 2
        credentials_path.unlink(missing_ok=True)
        set_future_env("KAGGLE_API_TOKEN", token_value.strip())
        set_future_env("KAGGLE_AUTH_MODE", "bearer-token")
    elif raw.startswith("KGAT_"):
        credentials_path.unlink(missing_ok=True)
        set_future_env("KAGGLE_API_TOKEN", raw)
        set_future_env("KAGGLE_AUTH_MODE", "bearer-token")
    else:
        # A legacy API key string needs the account username. The default is the
        # owner of the existing private Foundry kernel; override via KAGGLE_USERNAME.
        if not re.fullmatch(r"[A-Za-z0-9_-]+", owner):
            print("KAGGLE_AUTH_FAILED: legacy username is invalid", file=sys.stderr)
            return 2
        credentials_path.write_text(json.dumps({"username": owner, "key": raw}), encoding="utf-8")
        credentials_path.chmod(0o600)
        set_future_env("KAGGLE_API_TOKEN", "")
        set_future_env("KAGGLE_AUTH_MODE", "legacy-key")
    print("KAGGLE_AUTH_CONFIGURED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
