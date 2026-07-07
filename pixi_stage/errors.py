"""Typed exceptions carrying process exit codes and optional user hints."""


class PixiStageError(Exception):
    """Base error. exit_code maps to the process exit status."""

    exit_code = 1

    def __init__(self, message, *, hint=None):
        super().__init__(message)
        self.message = message
        self.hint = hint


class UsageError(PixiStageError):
    """Bad CLI arguments / inputs."""

    exit_code = 2


class PreconditionError(PixiStageError):
    """A precondition failed (no workspace, noarch recipe, src outside root, ...)."""

    exit_code = 3


class ValidationError(PixiStageError):
    """A post-edit validation (e.g. dual-mode render) failed."""

    exit_code = 4


class ExternalToolError(PixiStageError):
    """An external tool (git / pixi / rattler-build) failed or is missing."""

    exit_code = 5
