"""Edit the workspace ROOT pixi.toml: build-variants + root dependencies.

`pixi add` has no --path for conda source deps and there's no CLI for
[workspace.build-variants], so these are done by format-preserving TOML edits (tomlkit).
"""

from pathlib import Path

import tomlkit

from . import ops


def _ensure_table(parent, key):
    if key not in parent:
        parent[key] = tomlkit.table()
    return parent[key]


def ensure_preview(root_pixi, ctx, feature="pixi-build"):
    """Ensure `[workspace] preview` contains the given feature (pixi-build)."""
    path = Path(root_pixi)
    doc = tomlkit.parse(path.read_text())
    ws = _ensure_table(doc, "workspace")
    preview = ws.get("preview")
    if preview is None:
        ws["preview"] = [feature]
    elif feature in [str(x) for x in preview]:
        return False
    else:
        preview.append(feature)
    return ops.write_text(path, tomlkit.dumps(doc), ctx)


def set_build_variant(root_pixi, var_name, abs_path, ctx):
    path = Path(root_pixi)
    doc = tomlkit.parse(path.read_text())
    ws = _ensure_table(doc, "workspace")
    bv = _ensure_table(ws, "build-variants")
    if var_name in bv and list(bv[var_name]) == [abs_path]:
        return False
    bv[var_name] = [abs_path]
    return ops.write_text(path, tomlkit.dumps(doc), ctx)


def remove_build_variant(root_pixi, var_name, ctx):
    path = Path(root_pixi)
    doc = tomlkit.parse(path.read_text())
    bv = doc.get("workspace", {}).get("build-variants")
    if not bv or var_name not in bv:
        return False
    del bv[var_name]
    return ops.write_text(path, tomlkit.dumps(doc), ctx)


def set_dependency(root_pixi, package, rel_path, ctx):
    path = Path(root_pixi)
    doc = tomlkit.parse(path.read_text())
    deps = _ensure_table(doc, "dependencies")
    it = tomlkit.inline_table()
    it["path"] = rel_path
    cur = deps.get(package)
    if cur is not None and dict(cur) == {"path": rel_path}:
        return False
    deps[package] = it
    return ops.write_text(path, tomlkit.dumps(doc), ctx)


def remove_dependency(root_pixi, package, ctx):
    path = Path(root_pixi)
    doc = tomlkit.parse(path.read_text())
    deps = doc.get("dependencies")
    if not deps or package not in deps:
        return False
    del deps[package]
    return ops.write_text(path, tomlkit.dumps(doc), ctx)
