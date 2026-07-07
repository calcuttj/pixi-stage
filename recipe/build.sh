#!/bin/bash
set -euo pipefail

# Install the package + its console scripts (pixi-stage, pixi-unstage) from pyproject.
$PYTHON -m pip install . --no-deps --no-build-isolation -vv
