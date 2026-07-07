"""Run context, rollback journal, and dry-run-aware file mutations.

Every mutation goes through here so `--dry-run` (print a unified diff, touch nothing)
and rollback-on-failure fall out of a single code path.
"""

import difflib
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path


class Journal:
    """Records undo callables applied this run; replays them in reverse on failure."""

    def __init__(self):
        self._undos = []

    def record(self, undo):
        self._undos.append(undo)

    def rollback(self):
        while self._undos:
            undo = self._undos.pop()
            try:
                undo()
            except Exception:
                pass


@dataclass
class RunCtx:
    dry_run: bool = False
    verbose: bool = False
    journal: Journal = field(default_factory=Journal)


def _print_diff(path, old, new):
    old_lines = (old or "").splitlines(keepends=True)
    new_lines = (new or "").splitlines(keepends=True)
    rel = str(path)
    diff = difflib.unified_diff(old_lines, new_lines, fromfile=f"a/{rel}", tofile=f"b/{rel}")
    text = "".join(diff)
    if text and not text.endswith("\n"):
        text += "\n"
    sys.stdout.write(text)


def write_text(path, new_content, ctx):
    """Write new_content to path (create or modify). No-op if unchanged. Returns True if it changed."""
    path = Path(path)
    old = path.read_text() if path.exists() else None
    if old == new_content:
        return False
    label = "create" if old is None else "modify"
    if ctx.dry_run:
        print(f"[dry-run] would {label}: {path}")
        _print_diff(path, old, new_content)
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(new_content)
    if old is None:
        ctx.journal.record(lambda: path.unlink() if path.exists() else None)
    else:
        ctx.journal.record(lambda: path.write_text(old))
    if ctx.verbose:
        print(f"{label}d: {path}")
    return True


def remove_file(path, ctx):
    """Delete a file; restore it on rollback."""
    path = Path(path)
    if not path.exists():
        return False
    old = path.read_text()
    if ctx.dry_run:
        print(f"[dry-run] would remove: {path}")
        return True
    path.unlink()
    ctx.journal.record(lambda: path.write_text(old))
    if ctx.verbose:
        print(f"removed: {path}")
    return True


def remove_tree(path, ctx):
    """Delete a directory tree (used by `unstage --remove-feedstock`). Not rollback-able."""
    path = Path(path)
    if not path.exists():
        return False
    if ctx.dry_run:
        print(f"[dry-run] would remove: {path}")
        return True
    shutil.rmtree(path)
    if ctx.verbose:
        print(f"removed: {path}")
    return True
