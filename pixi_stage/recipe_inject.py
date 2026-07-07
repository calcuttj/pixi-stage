"""Inject the dev-source build-variant switch into a feedstock recipe.yaml (idempotent).

Adds `dev_src: ${{ <var> | default("") }}` to `context:` and rewrites a flat url source
into the conditional form:

    source:
      - if: dev_src == ""
        then: { <original url mapping, verbatim> }
        else: { path: ${{ dev_src }} }

Round-trips with ruamel so comments / quoting / other jinja survive. Re-running is a no-op.
"""

from io import StringIO
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from . import ops
from .errors import PreconditionError

_DEV_COMMENT = (
    "Development override (managed by pixi-stage): dev_src is a build VARIANT.\n"
    'Unset (conda-forge CI) => tagged tarball; set via [workspace.build-variants]\n'
    "to build from a local checkout (also gives the dev build a distinct hash)."
)


def _rt_yaml():
    y = YAML()  # round-trip
    y.preserve_quotes = True
    y.width = 4096
    # Match the conda-forge / rattler recipe block style (sequences indented under
    # their key) so injecting touches only the lines we change, not the whole file.
    y.indent(mapping=2, sequence=4, offset=2)
    return y


def _source_already_injected(src):
    if isinstance(src, list):
        for item in src:
            if isinstance(item, dict) and "if" in item and "dev_src" in str(item.get("if", "")):
                return True
    return False


def _build_conditional(orig_map):
    item = CommentedMap()
    item["if"] = 'dev_src == ""'
    item["then"] = orig_map
    els = CommentedMap()
    els["path"] = "${{ dev_src }}"
    item["else"] = els
    seq = CommentedSeq()
    seq.append(item)
    return seq


def _transform_source(data):
    if "source" not in data:
        raise PreconditionError("recipe has no `source:` — cannot inject the dev-source switch.")
    src = data["source"]
    if _source_already_injected(src):
        return False
    if isinstance(src, dict):
        if "url" in src:
            data["source"] = _build_conditional(src)
            return True
        raise PreconditionError(
            "recipe `source` is not a url source (git/path) — auto-inject unsupported.",
            hint="Add the `dev_src` conditional to the recipe by hand.",
        )
    if isinstance(src, list):
        real = [i for i in src if isinstance(i, dict)]
        if len(real) == 1 and "url" in real[0]:
            data["source"] = _build_conditional(real[0])
            return True
        raise PreconditionError(
            "recipe has multiple/complex sources — auto-inject unsupported.",
            hint="Add the `dev_src` conditional to the recipe by hand.",
        )
    raise PreconditionError("unrecognized `source` shape in recipe.")


def inject(recipe_path, var_name, ctx):
    """Ensure the recipe carries the dev_src variable + conditional source. Returns True if changed."""
    recipe_path = Path(recipe_path)
    y = _rt_yaml()
    with open(recipe_path) as f:
        data = y.load(f)

    changed = False

    if "context" not in data:
        data.insert(0, "context", CommentedMap())
        changed = True
    context = data["context"]
    if "dev_src" not in context:
        context["dev_src"] = '${{ %s | default("") }}' % var_name
        try:
            context.yaml_set_comment_before_after_key("dev_src", before=_DEV_COMMENT, indent=2)
        except Exception:
            pass
        changed = True

    changed = _transform_source(data) or changed

    if not changed:
        return False

    buf = StringIO()
    y.dump(data, buf)
    return ops.write_text(recipe_path, buf.getvalue(), ctx)
