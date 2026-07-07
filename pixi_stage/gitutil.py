"""Thin git wrapper. All calls raise ExternalToolError on failure or missing git."""

import subprocess
from pathlib import Path

from .errors import ExternalToolError


def _run(args, cwd=None):
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    except FileNotFoundError:
        raise ExternalToolError("`git` not found on PATH; install git or reinstall pixi-stage.")
    if r.returncode != 0:
        raise ExternalToolError(f"git {' '.join(args[1:])} failed:\n{r.stderr.strip()}")
    return r.stdout


def is_repo(path):
    return (Path(path) / ".git").exists()


def clone(url, dest):
    _run(["git", "clone", url, str(dest)])


def fetch(repo):
    _run(["git", "fetch", "--all", "--tags"], cwd=str(repo))


def checkout(repo, ref):
    _run(["git", "checkout", ref], cwd=str(repo))


def checkout_file(repo, relpath):
    """Restore a tracked file to its committed state (used to revert recipe injection)."""
    _run(["git", "checkout", "--", relpath], cwd=str(repo))


def status_porcelain(repo):
    return _run(["git", "status", "--porcelain"], cwd=str(repo))
