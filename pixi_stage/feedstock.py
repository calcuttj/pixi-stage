"""Obtain a feedstock checkout, gate on noarch, and read the package version."""

from pathlib import Path

from ruamel.yaml import YAML

from . import gitutil, ops
from .errors import PreconditionError

_yaml_safe = YAML(typ="safe")


def member_dir_for(root, package):
    return Path(root) / f"{package}-feedstock"


def recipe_path_for(member_dir):
    return Path(member_dir) / "recipe" / "recipe.yaml"


def load_recipe(recipe_path):
    recipe_path = Path(recipe_path)
    if not recipe_path.exists():
        raise PreconditionError(f"recipe not found: {recipe_path}")
    with open(recipe_path) as f:
        return _yaml_safe.load(f)


def obtain(package, member_dir, url, rev, ctx):
    """Clone the feedstock if absent; otherwise reuse it (checkout `rev` if given)."""
    member_dir = Path(member_dir)
    if member_dir.exists():
        if not gitutil.is_repo(member_dir) and not (member_dir / "recipe").exists():
            raise PreconditionError(
                f"{member_dir} exists but is not a feedstock checkout.",
                hint="Remove or rename it, then re-run.",
            )
        if rev and gitutil.is_repo(member_dir):
            gitutil.fetch(member_dir)
            gitutil.checkout(member_dir, rev)
        return member_dir

    if ctx.dry_run:
        print(f"[dry-run] would clone {url} -> {member_dir}")
        raise PreconditionError(
            f"--dry-run cannot preview edits before the feedstock is cloned ({member_dir} absent).",
            hint="Run without --dry-run to clone, or clone the feedstock manually first.",
        )

    gitutil.clone(url, member_dir)
    ctx.journal.record(lambda: ops.remove_tree(member_dir, ctx))
    if rev:
        gitutil.checkout(member_dir, rev)
    return member_dir


def noarch_gate(recipe_data, package):
    build = recipe_data.get("build") or {}
    if isinstance(build, dict) and "noarch" in build:
        raise PreconditionError(
            f"{package} is a noarch recipe; source-building noarch is unsupported by "
            f"pixi-build-rattler-build (known backend bug — see PIXI_BUILD_NOARCH_BUG.md).",
            hint=f"Consume it from a channel instead:  pixi add {package}",
        )


def read_version(recipe_data, package):
    context = recipe_data.get("context") or {}
    v = context.get("version")
    if isinstance(v, str) and "${{" not in v:
        return v
    pv = (recipe_data.get("package") or {}).get("version")
    if isinstance(pv, str) and "${{" not in pv:
        return pv
    raise PreconditionError(
        f"Could not read a literal version for {package} from the recipe "
        f"(context.version / package.version).",
        hint="Ensure the recipe's context defines a plain `version:` string.",
    )
