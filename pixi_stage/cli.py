"""Command-line entry point.

pixi discovers `pixi <name>` -> `pixi-<name>` on PATH. The single `pixi-stage`
executable is a subcommand dispatcher, so:
  * `pixi stage add <package> [--src ...]`   stage a package
  * `pixi stage rm <package>`                unstage (reverse a stage)
  * `pixi stage wire`                        reconcile the dependency graph
"""

import argparse
import sys

from . import __version__, feedstock, member_manifest, ops, recipe_inject, root_manifest
from . import srcpath, validate, wire
from .config import load_config
from .errors import PixiStageError
from .ops import RunCtx
from .workspace import find_workspace_root, workspace_channels


def _emit_error(e):
    sys.stderr.write(f"error: {e.message}\n")
    if e.hint:
        sys.stderr.write(f"hint:  {e.hint}\n")


def _run(fn):
    try:
        fn()
        return 0
    except PixiStageError as e:
        _emit_error(e)
        sys.exit(e.exit_code)


def _var_name(package):
    return package.replace("-", "_") + "_dev_src"


# --------------------------------------------------------------------------- add

def _do_add(args, ctx):
    root = find_workspace_root()
    cfg = load_config(root, overrides={
        "feedstock-url-template": args.feedstock_url,
        "default-feedstock-rev": args.feedstock_rev,
    })
    package = args.package
    var = _var_name(package)
    member_dir = feedstock.member_dir_for(root, package)
    url = cfg.feedstock_url_template.format(package=package)
    rev = args.feedstock_rev or (cfg.default_feedstock_rev or None)

    # Validate --src up front (fail fast, before any mutation).
    src_abs = srcpath.resolve_under_workspace(args.src, root) if args.src else None

    # The build backend only engages when the workspace opts into the preview feature.
    root_manifest.ensure_preview(root / "pixi.toml", ctx)

    feedstock.obtain(package, member_dir, url, rev, ctx)
    recipe_path = feedstock.recipe_path_for(member_dir)
    data = feedstock.load_recipe(recipe_path)
    feedstock.noarch_gate(data, package)
    version = feedstock.read_version(data, package)

    recipe_inject.inject(recipe_path, var, ctx)
    member_manifest.bootstrap(member_dir, package, version, cfg.backend, cfg.extra_input_globs, ctx)

    if src_abs:
        root_manifest.set_build_variant(root / "pixi.toml", var, src_abs, ctx)

    root_manifest.set_dependency(root / "pixi.toml", package, member_dir.name, ctx)

    for dep in (args.dependent or []):
        wire.add_dependent(root, package, dep, ctx)

    if not args.no_wire:
        wire.reconcile(root, ctx)

    if cfg.validate and not args.no_validate and not ctx.dry_run:
        res = validate.validate(recipe_path, package, var, src_abs, workspace_channels(root))
        if src_abs:
            print(f"validated: release={res['release_hash']}  dev={res['dev_hash']} (distinct)")
        else:
            print(f"validated: release={res['release_hash']}")

    mode = "dev (local source)" if src_abs else "release (tarball)"
    if ctx.dry_run:
        print(f"\n[dry-run] would stage '{package}' in {mode} mode — no files changed.")
    else:
        print(f"\nStaged '{package}' ({mode}). Build/refresh the env with:  pixi install")


# --------------------------------------------------------------------------- rm

def _do_rm(args, ctx):
    from . import gitutil

    root = find_workspace_root()
    package = args.package
    var = _var_name(package)
    member_dir = feedstock.member_dir_for(root, package)

    root_manifest.remove_dependency(root / "pixi.toml", package, ctx)
    root_manifest.remove_build_variant(root / "pixi.toml", var, ctx)

    if args.remove_feedstock:
        ops.remove_tree(member_dir, ctx)
    else:
        recipe_rel = "recipe/recipe.yaml"
        recipe_path = member_dir / recipe_rel
        if gitutil.is_repo(member_dir) and recipe_path.exists():
            old = recipe_path.read_text()
            if ctx.dry_run:
                print(f"[dry-run] would revert {recipe_path} to its committed state")
            else:
                gitutil.checkout_file(member_dir, recipe_rel)
                ctx.journal.record(lambda: recipe_path.write_text(old))
        ops.remove_file(member_dir / "pixi.toml", ctx)

    # Re-wire so consumers drop their now-stale path deps to this package.
    wire.reconcile(root, ctx)

    if ctx.dry_run:
        print(f"\n[dry-run] would unstage '{package}' — no files changed.")
    else:
        print(f"\nUnstaged '{package}'. Refresh the env with:  pixi install")


# --------------------------------------------------------------------------- wire

def _do_wire(args, ctx):
    root = find_workspace_root()
    changed = wire.reconcile(root, ctx)
    if ctx.dry_run:
        print("[dry-run] wire reconciliation preview complete.")
    else:
        print("Wire reconciliation complete." + ("" if changed else " (no changes)"))


# --------------------------------------------------------------------------- parser / dispatch

_HANDLERS = {"add": _do_add, "rm": _do_rm, "wire": _do_wire}


def _add_common(p):
    p.add_argument("--dry-run", action="store_true", help="show planned edits (diffs) without applying")
    p.add_argument("-v", "--verbose", action="store_true")


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="pixi stage",
        description="Stage conda packages into the active pixi workspace as editable, source-built dependencies.",
    )
    parser.add_argument("--version", action="version", version=f"pixi-stage {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True, metavar="{add,rm,wire}")

    add_p = sub.add_parser("add", help="stage a package as an editable, source-built dependency")
    add_p.add_argument("package", help="conda package name (feedstock is <package>-feedstock)")
    add_p.add_argument("--src", help="local source checkout to build from (must be under the workspace root)")
    add_p.add_argument("--feedstock-rev", help="git ref (tag/branch/SHA) to check the feedstock out at")
    add_p.add_argument("--feedstock-url", help="feedstock URL template ({package} is substituted)")
    add_p.add_argument("--dependent", action="append", metavar="MEMBER",
                       help="also wire this package into MEMBER's host+run deps (repeatable)")
    add_p.add_argument("--no-wire", action="store_true", help="skip automatic dependency-graph reconciliation")
    add_p.add_argument("--no-validate", action="store_true", help="skip the rattler-build render checks")
    _add_common(add_p)

    rm_p = sub.add_parser("rm", help="unstage a package (reverse a stage)")
    rm_p.add_argument("package")
    rm_p.add_argument("--remove-feedstock", action="store_true", help="also delete the <package>-feedstock directory")
    _add_common(rm_p)

    wire_p = sub.add_parser("wire", help="reconcile the inter-member path-dependency graph from the recipes")
    _add_common(wire_p)

    return parser


def _dispatch(args):
    ctx = RunCtx(dry_run=args.dry_run, verbose=args.verbose)
    try:
        _HANDLERS[args.cmd](args, ctx)
    except BaseException:
        ctx.journal.rollback()
        raise


def stage_main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    args = _build_parser().parse_args(argv)
    return _run(lambda: _dispatch(args))
