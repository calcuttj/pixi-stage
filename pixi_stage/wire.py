"""Reconcile the inter-member path-dependency graph from the members' recipes.

For every staged member A, any requirement that is ALSO a staged package B is wired as a
`B = { path = "../B-feedstock" }` dep in A's matching table (build/host/run). Requirements
on non-staged packages stay channel binaries. Stale sibling path deps (to packages no longer
staged) are removed. Idempotent; run after every stage/unstage.
"""

import os
from pathlib import Path

import tomlkit

from . import ops, reqs
from .errors import PreconditionError

SECTION_TABLE = {
    "build": "build-dependencies",
    "host": "host-dependencies",
    "run": "run-dependencies",
}


def discover_members(root):
    """name -> member dir Path, for every subdir whose pixi.toml declares [package].name."""
    root = Path(root)
    members = {}
    for child in sorted(p for p in root.iterdir() if p.is_dir()):
        manifest = child / "pixi.toml"
        if not manifest.exists():
            continue
        try:
            doc = tomlkit.parse(manifest.read_text())
        except Exception:
            continue
        pkg = doc.get("package")
        if pkg and "name" in pkg:
            members[str(pkg["name"])] = child
    return members


def _is_sibling_pathdep(value):
    """A dep value we manage: an inline table {path = "../<x>-feedstock"}."""
    if not isinstance(value, dict) or "path" not in value:
        return False
    p = str(value["path"])
    return p.startswith("../") and p.endswith("-feedstock")


def _reconcile_member(name, mdir, members, ctx):
    manifest = mdir / "pixi.toml"
    doc = tomlkit.parse(manifest.read_text())
    pkg = doc.get("package")
    if pkg is None:
        return False
    recipe = mdir / "recipe" / "recipe.yaml"
    r = reqs.parse_requirements(recipe) if recipe.exists() else {s: set() for s in reqs.SECTIONS}
    dirty = False

    # Add edges: requirement that is also a staged sibling -> path dep in the matching table.
    for sect, table_key in SECTION_TABLE.items():
        for dep in sorted(r[sect]):
            if dep == name or dep not in members:
                continue
            rel = os.path.relpath(members[dep], mdir)
            tbl = pkg.get(table_key)
            if tbl is None:
                tbl = tomlkit.table()
                pkg[table_key] = tbl
            cur = tbl.get(dep)
            if cur is not None and dict(cur) == {"path": rel}:
                continue
            it = tomlkit.inline_table()
            it["path"] = rel
            tbl[dep] = it
            dirty = True

    # Remove stale managed sibling path deps whose target is no longer a staged member.
    for table_key in SECTION_TABLE.values():
        tbl = pkg.get(table_key)
        if tbl is None:
            continue
        for dep in list(tbl.keys()):
            if dep not in members and _is_sibling_pathdep(tbl.get(dep)):
                del tbl[dep]
                dirty = True

    if not dirty:
        return False
    return ops.write_text(manifest, tomlkit.dumps(doc), ctx)


def reconcile(root, ctx):
    members = discover_members(root)
    changed = False
    for name, mdir in members.items():
        if _reconcile_member(name, mdir, members, ctx):
            changed = True
    return changed


def add_dependent(root, package, dependent_member, ctx, sections=("host", "run")):
    """Manual override: force-wire `package` into `dependent_member`'s host+run path deps."""
    members = discover_members(root)
    if dependent_member not in members:
        raise PreconditionError(
            f"--dependent target '{dependent_member}' is not a staged member.",
            hint="Stage the dependent first, or check the package name.",
        )
    if package not in members:
        raise PreconditionError(f"'{package}' is not a staged member yet.")
    mdir = members[dependent_member]
    manifest = mdir / "pixi.toml"
    doc = tomlkit.parse(manifest.read_text())
    pkg = doc["package"]
    rel = os.path.relpath(members[package], mdir)
    dirty = False
    for sect in sections:
        table_key = SECTION_TABLE[sect]
        tbl = pkg.get(table_key)
        if tbl is None:
            tbl = tomlkit.table()
            pkg[table_key] = tbl
        cur = tbl.get(package)
        if cur is not None and dict(cur) == {"path": rel}:
            continue
        it = tomlkit.inline_table()
        it["path"] = rel
        tbl[package] = it
        dirty = True
    if not dirty:
        return False
    return ops.write_text(manifest, tomlkit.dumps(doc), ctx)
