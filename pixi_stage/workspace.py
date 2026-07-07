"""Locate the active pixi workspace root and read workspace-level fields."""

from pathlib import Path

import tomlkit

from .errors import PreconditionError


def find_workspace_root(start=None):
    """Walk up from `start` (default cwd) to the nearest pixi.toml with a [workspace] table."""
    start = Path(start or Path.cwd()).resolve()
    for d in [start, *start.parents]:
        manifest = d / "pixi.toml"
        if not manifest.exists():
            continue
        try:
            data = tomlkit.parse(manifest.read_text())
        except Exception:
            continue
        if "workspace" in data:
            return d
    raise PreconditionError(
        f"No pixi workspace found at or above {start}",
        hint="cd into your pixi workspace (a directory whose pixi.toml has a [workspace] table).",
    )


def workspace_channels(root):
    data = tomlkit.parse((Path(root) / "pixi.toml").read_text())
    ws = data.get("workspace", {})
    return [str(c) for c in ws.get("channels", [])]
