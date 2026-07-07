"""Parse plain package-name requirements from a rattler-build recipe.

Used by wire.py to induce the inter-member path-dep graph. Skips jinja
(`${{ ... }}`), `compiler(...)`/`pin_*(...)` helpers, and flattens `if/then/else`
conditional list entries.
"""

from ruamel.yaml import YAML

_yaml_safe = YAML(typ="safe")

SECTIONS = ("build", "host", "run")


def _flatten(items):
    out = []
    for it in items or []:
        if isinstance(it, str):
            out.append(it)
        elif isinstance(it, dict):
            for key in ("then", "else"):
                v = it.get(key)
                if isinstance(v, list):
                    out.extend(_flatten(v))
                elif isinstance(v, str):
                    out.append(v)
    return out


def _dep_name(entry):
    if not isinstance(entry, str):
        return None
    s = entry.strip()
    if not s or "${{" in s:
        return None
    tok = s.split()[0]  # drop version constraint
    if "(" in tok or ")" in tok:  # compiler(...), pin_subpackage(...), ...
        return None
    return tok


def parse_requirements(recipe_path):
    with open(recipe_path) as f:
        data = _yaml_safe.load(f) or {}
    reqs = data.get("requirements") or {}
    out = {s: set() for s in SECTIONS}
    for sect in SECTIONS:
        for entry in _flatten(reqs.get(sect) or []):
            name = _dep_name(entry)
            if name:
                out[sect].add(name)
    return out
