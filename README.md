# pixi-stage

A [pixi](https://pixi.sh) extension that stages a conda package into your active pixi
workspace as an **editable, source-built dependency** — reusing the package's conda-forge
feedstock recipe (one recipe, no copies) so the same recipe serves conda-forge CI and local
development.

## Install

```bash
git clone git@github.com:calcuttj/pixi-stage pixi-stage-src
rattler-build build --recipe pixi-stage-src/recipe/recipe.yaml --output-dir pixi-stage-output
pixi global install pixi-stage --channel file://$PWD/pixi-stage-output/ --channel conda-forge        # provides the `pixi stage` subcommands
```

## Use

`pixi stage` is a subcommand dispatcher: `add`, `rm`, `wire`.

```bash
# Stage a package for local development against an edited checkout:
pixi stage add dune-justin --src dune-justin-feedstock/src-checkout
pixi install                          # builds it from your source

# Stage from the released tarball (no local edits), just to co-build/coordinate:
pixi stage add dunecore

# Reconcile the inter-package graph on demand (also runs automatically after add/rm):
pixi wire

# Reverse it:
pixi stage rm dune-justin
```

What `pixi stage add <package>` does:
1. Clones `conda-forge/<package>-feedstock` into the workspace as `<package>-feedstock/` (reused recipe).
2. Bootstraps a member `pixi.toml` (backend + `extra-input-globs`).
3. Injects a `dev_src` **build variant** switch into the recipe (idempotent) — the dev build
   gets a distinct hash so it never collides with the release in the cache.
4. With `--src`: registers the checkout in `[workspace.build-variants]` and adds the package
   to the root `[dependencies]`.
5. **Auto-wires** the dependency graph: any staged package that another staged member depends
   on (per its recipe `requirements`) is wired as a `path=` source dep in the matching table,
   so consumers build against your local source. `--dependent <member>` forces an edge manually.

## Constraints

- **arch packages only** for source builds. A `noarch:` recipe is refused (a
  `pixi-build-rattler-build` backend bug fails noarch source builds — see the report the
  refusal points at). Consume noarch/foundational packages from a channel instead.
- **`--src` must be under the workspace root** (a `path:` source makes rattler-build walk the
  common-ancestor tree; external paths can trip on unrelated symlink loops).

## Flags

`--src` · `--feedstock-rev <ref>` · `--feedstock-url <template>` · `--dependent <member>` ·
`--no-wire` · `--no-validate` · `--dry-run` · `-v/--verbose`.

Config (optional): `<workspace>/.pixi-stage.toml` or `~/.config/pixi-stage/config.toml`
(`feedstock-url-template`, `default-feedstock-rev`, `validate`, `backend`, `extra-input-globs`).
