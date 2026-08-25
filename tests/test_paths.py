"""Tests for safe_output_path's containment guarantee.

Ported alongside the function itself from proposal-wizard (see
docs/RECONVERGENCE_ASSESSMENT.md §3.4).

Every assertion resolves both sides before comparing. On macOS the temp
directory is reached through symlinks (/tmp -> /private/tmp), so comparing a
resolved result against an unresolved fixture path yields a mismatch that
looks like a containment bug but is only a symlink artifact.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from wizard_core.paths import safe_output_path


@pytest.fixture
def root(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    return project.resolve()


def test_relative_path_resolves_under_root(root: Path) -> None:
    assert safe_output_path(root, "deck.pptx") == root / "deck.pptx"


def test_nested_relative_path(root: Path) -> None:
    result = safe_output_path(root, "sections/intro/body.md")
    assert result == root / "sections" / "intro" / "body.md"
    # The guard does not create anything.
    assert not result.exists()
    assert not (root / "sections").exists()


def test_accepts_path_objects(root: Path) -> None:
    assert safe_output_path(root, Path("a/b.txt")) == root / "a" / "b.txt"
    assert safe_output_path(str(root), "a/b.txt") == root / "a" / "b.txt"


def test_traversal_that_stays_inside_is_allowed(root: Path) -> None:
    """`a/../b` normalizes to root/b — legitimate, not an escape."""
    assert safe_output_path(root, "a/../b.txt") == root / "b.txt"


@pytest.mark.parametrize(
    "requested",
    [
        "../escape.txt",
        "../../escape.txt",
        "sections/../../escape.txt",
        "../",
        "..",
    ],
)
def test_parent_traversal_is_rejected(root: Path, requested: str) -> None:
    with pytest.raises(ValueError, match="escapes"):
        safe_output_path(root, requested)


@pytest.mark.parametrize("requested", ["/etc/passwd", "/tmp/evil.txt"])
def test_absolute_paths_are_rejected(root: Path, requested: str) -> None:
    with pytest.raises(ValueError, match="must be relative"):
        safe_output_path(root, requested)


def test_absolute_path_inside_root_is_still_rejected(root: Path) -> None:
    """Rejected on the absolute-path rule before containment is considered."""
    with pytest.raises(ValueError, match="must be relative"):
        safe_output_path(root, str(root / "inside.txt"))


def test_symlink_escaping_root_is_rejected(root: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "link").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="escapes"):
        safe_output_path(root, "link/stolen.txt")


def test_sibling_directory_sharing_a_name_prefix_is_rejected(
    root: Path, tmp_path: Path
) -> None:
    """`project-evil` must not count as inside `project`.

    A containment check written as a string-prefix comparison would accept
    this; component-wise comparison rejects it.
    """
    evil = tmp_path / "project-evil"
    evil.mkdir()
    (root / "link").symlink_to(evil, target_is_directory=True)
    with pytest.raises(ValueError, match="escapes"):
        safe_output_path(root, "link/x.txt")
    with pytest.raises(ValueError, match="escapes"):
        safe_output_path(root, "../project-evil/x.txt")


def test_symlink_inside_root_is_allowed(root: Path) -> None:
    """Resolution must not reject a symlink that stays within the project."""
    (root / "real").mkdir()
    (root / "alias").symlink_to(root / "real", target_is_directory=True)
    assert safe_output_path(root, "alias/note.md") == root / "real" / "note.md"


def test_root_need_not_exist(tmp_path: Path) -> None:
    missing = tmp_path / "not-created-yet"
    assert safe_output_path(missing, "out.txt") == missing.resolve() / "out.txt"


def test_empty_request_returns_root(root: Path) -> None:
    """Documents current behavior: "" resolves to the root itself."""
    assert safe_output_path(root, "") == root
