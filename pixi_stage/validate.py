"""Validate a staged recipe by rendering it in both modes with rattler-build.

Release (no variant) must resolve to a url source; dev (variant set) must resolve to a
path source with a DIFFERENT build hash (proving the variant reaches the render and won't
collide with the release in the cache).
"""

import json
import subprocess
import tempfile
from pathlib import Path

from .errors import ExternalToolError, ValidationError


def _render(recipe_path, channels, variant_file=None):
    args = ["rattler-build", "build", "--recipe", str(recipe_path), "--render-only"]
    for c in channels:
        args += ["-c", c]
    if variant_file:
        args += ["--variant-config", str(variant_file)]
    try:
        r = subprocess.run(args, capture_output=True, text=True)
    except FileNotFoundError:
        raise ExternalToolError("`rattler-build` not found on PATH; reinstall pixi-stage.")
    if r.returncode != 0:
        raise ExternalToolError(f"rattler-build render failed:\n{r.stderr.strip()[:800]}")
    out = r.stdout
    i = out.find("[")
    if i < 0:
        raise ValidationError("could not parse rattler-build --render-only output (no JSON).")
    data = json.loads(out[i:])
    o = data[0]
    src = o["recipe"]["source"]
    bstring = o["build_configuration"]["subpackages"]
    return src, bstring


def _build_string(subpackages, package):
    sp = subpackages.get(package)
    if not sp:
        # fall back to the sole subpackage if the name key differs
        if len(subpackages) == 1:
            sp = next(iter(subpackages.values()))
        else:
            raise ValidationError(f"render has no subpackage '{package}'.")
    return sp["build_string"]


def _has_key(src, key):
    return isinstance(src, list) and any(isinstance(i, dict) and key in i for i in src)


def validate(recipe_path, package, var_name, src_abs, channels):
    """Returns {'release_hash':..., 'dev_hash':...(if src_abs)}. Raises ValidationError on mismatch."""
    rel_src, rel_bs = _render(recipe_path, channels)
    if not _has_key(rel_src, "url"):
        raise ValidationError("release render did not resolve to a url source.")
    result = {"release_hash": _build_string(rel_bs, package)}

    if not src_abs:
        return result

    with tempfile.TemporaryDirectory(prefix="pixi-stage-") as td:
        vf = Path(td) / "variant.yaml"
        vf.write_text('%s:\n  - "%s"\n' % (var_name, src_abs))
        dev_src, dev_bs = _render(recipe_path, channels, vf)

    if not _has_key(dev_src, "path"):
        raise ValidationError("dev render did not resolve to a path source.")
    result["dev_hash"] = _build_string(dev_bs, package)
    if result["release_hash"] == result["dev_hash"]:
        raise ValidationError(
            "variant did not change the build hash — the dev build would collide with the "
            "release in the cache (injection ineffective)."
        )
    return result
