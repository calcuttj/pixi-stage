"""Bootstrap / maintain a member `pixi.toml` at a feedstock checkout root.

Feedstocks never ship a pixi.toml, so this creates the thin manifest the
pixi-build-rattler-build backend needs. Idempotent: merges required tables/keys
without clobbering user additions.
"""

from pathlib import Path

import tomlkit

from . import ops


def _ensure_table(parent, key):
    if key not in parent:
        parent[key] = tomlkit.table()
    return parent[key]


def bootstrap(member_dir, package, version, backend, extra_input_globs, ctx):
    path = Path(member_dir) / "pixi.toml"
    doc = tomlkit.parse(path.read_text()) if path.exists() else tomlkit.document()

    package_tbl = _ensure_table(doc, "package")
    package_tbl["name"] = package
    if "version" not in package_tbl:
        package_tbl["version"] = version

    build = _ensure_table(package_tbl, "build")
    be = tomlkit.inline_table()
    be["name"] = backend["name"]
    be["version"] = backend["version"]
    build["backend"] = be

    cfg = _ensure_table(build, "config")
    if "extra-input-globs" not in cfg:
        cfg["extra-input-globs"] = list(extra_input_globs)

    return ops.write_text(path, tomlkit.dumps(doc), ctx)
