"""Filesystem path safety helpers shared by the wizard tools.

Every wizard writes generated artifacts into an output project directory using
names that ultimately derive from user or model input — section names, source
ids, deck slugs. Those names must not be able to steer a write outside the
project.

`safe_output_path` is ported from proposal-wizard's
`proposal_wizard/pwiz_paths.py` (see docs/RECONVERGENCE_ASSESSMENT.md §3.4,
Phase 1), generalized here so slide-wizard and repo-research-writer get the
same guard. Behavior is unchanged apart from the error text, which no longer
names the proposal domain.
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

PathLike = Union[str, Path]

__all__ = ["PathLike", "safe_output_path"]


def safe_output_path(root: PathLike, requested: PathLike) -> Path:
    """Resolve ``requested`` under ``root`` and refuse to escape it.

    Absolute paths and parent-directory traversal are rejected before any
    directory or file is created. Existing symlinks in both ``root`` and the
    requested path are resolved before containment is checked, so a symlink
    already pointing outside the project cannot be used as a way out.

    Traversal that stays inside is allowed: ``a/../b`` normalizes to
    ``root/b``, which is a legitimate path, not an escape.

    Args:
        root: The output project directory that writes must stay within.
        requested: A relative path beneath ``root``.

    Returns:
        The resolved absolute path, guaranteed to be ``root`` or below it.

    Raises:
        ValueError: If ``requested`` is absolute or resolves outside ``root``.

    Note:
        The containment check reflects the filesystem at call time. It is not
        a defense against an attacker who can create symlinks under ``root``
        between this call and the subsequent write.
    """
    root_path = Path(root).resolve()
    requested_path = Path(requested)
    if requested_path.is_absolute():
        raise ValueError(
            f"Output path must be relative to {root_path}: {requested}"
        )

    output_path = (root_path / requested_path).resolve(strict=False)
    try:
        output_path.relative_to(root_path)
    except ValueError as exc:
        raise ValueError(
            f"Output path escapes the project directory {root_path}: {requested}"
        ) from exc

    return output_path
