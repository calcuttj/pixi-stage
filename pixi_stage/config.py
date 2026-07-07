"""pixi-stage configuration: its OWN config file (never pixi's config.toml).

Precedence (highest first): CLI overrides > workspace `.pixi-stage.toml` > global config > built-in defaults.
Global config location: $PIXI_HOME/pixi-stage/config.toml, else $XDG_CONFIG_HOME/pixi-stage/config.toml,
else ~/.config/pixi-stage/config.toml.
"""

import os
from dataclasses import dataclass
from pathlib import Path

import tomlkit

DEFAULTS = {
    "feedstock-url-template": "https://github.com/conda-forge/{package}-feedstock",
    "default-feedstock-rev": "",
    "validate": True,
    "backend": {"name": "pixi-build-rattler-build", "version": "*"},
    "extra-input-globs": ["recipe/**"],
}


def _load_toml(path):
    try:
        return dict(tomlkit.parse(Path(path).read_text()))
    except FileNotFoundError:
        return {}
    except Exception:
        return {}


def global_config_path():
    pixi_home = os.environ.get("PIXI_HOME")
    if pixi_home:
        return Path(pixi_home) / "pixi-stage" / "config.toml"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else (Path.home() / ".config")
    return base / "pixi-stage" / "config.toml"


@dataclass(frozen=True)
class Config:
    feedstock_url_template: str
    default_feedstock_rev: str
    validate: bool
    backend: dict
    extra_input_globs: list


def load_config(workspace_root=None, overrides=None):
    merged = dict(DEFAULTS)
    merged.update(_load_toml(global_config_path()))
    if workspace_root:
        merged.update(_load_toml(Path(workspace_root) / ".pixi-stage.toml"))
    if overrides:
        merged.update({k: v for k, v in overrides.items() if v is not None})
    return Config(
        feedstock_url_template=str(merged["feedstock-url-template"]),
        default_feedstock_rev=str(merged["default-feedstock-rev"]),
        validate=bool(merged["validate"]),
        backend=dict(merged["backend"]),
        extra_input_globs=list(merged["extra-input-globs"]),
    )
