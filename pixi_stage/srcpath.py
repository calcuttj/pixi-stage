"""Resolve a --src checkout and enforce the under-workspace-root policy.

A `path:` source makes rattler-build walk the common-ancestor tree of the source and the
output; external paths can trip on unrelated symlink loops. Verified: a source under the
workspace root builds clean, an external one fails. So we require --src under the root.
"""

from pathlib import Path

from .errors import PreconditionError, UsageError


def resolve_under_workspace(src, workspace_root):
    p = Path(src).expanduser()
    if not p.exists():
        raise UsageError(f"--src path does not exist: {src}")
    p = p.resolve()
    root = Path(workspace_root).resolve()
    if p != root and root not in p.parents:
        raise PreconditionError(
            f"--src ({p}) is outside the workspace root ({root}).",
            hint=(
                "Keep the checkout under the workspace so the path-source build walk stays local, "
                "e.g. clone/move it to <package>-feedstock/src-checkout (already gitignored), "
                "then pass that path."
            ),
        )
    return str(p)
