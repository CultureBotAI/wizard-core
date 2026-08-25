"""Smoke tests for GitManager safety and basic flow."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

import pytest

from wizard_core.git_manager import (
    DEFAULT_GITIGNORE,
    GitManager,
    GitSafetyError,
    ToolGuard,
    default_whitelist_lines,
)


def _is_ignored(repo: Path, relpath: str) -> bool:
    """True if git would ignore `relpath` inside `repo`."""
    result = subprocess.run(
        ["git", "-C", str(repo), "check-ignore", "-q", relpath],
        capture_output=True,
        check=False,
    )
    assert result.returncode in (0, 1), result.stderr.decode()
    return result.returncode == 0


@pytest.fixture
def guard() -> ToolGuard:
    return ToolGuard(
        tool_name="testtool",
        state_dir_name=".testtool",
        tool_repo_markers=("scripts/testtool_marker.py",),
        remote_url_patterns=("github.com/example/testtool",),
    )


def test_refuses_tool_repo(tmp_path: Path, guard: ToolGuard) -> None:
    fake_tool = tmp_path / "tool"
    (fake_tool / "scripts").mkdir(parents=True)
    (fake_tool / "scripts" / "testtool_marker.py").write_text("# marker")
    with pytest.raises(GitSafetyError):
        GitManager(project_dir=fake_tool, guard=guard)


def test_initialize_repository_and_commit(tmp_path: Path, guard: ToolGuard) -> None:
    proj = tmp_path / "proj"
    proj.mkdir()
    mgr = GitManager(project_dir=proj, guard=guard, verbose=False)
    assert mgr.initialize_repository()
    assert (proj / ".git").is_dir()
    # Already initialized -> second call returns False
    assert not mgr.initialize_repository()

    (proj / "hello.txt").write_text("hi")
    commit = mgr.commit(
        files=["hello.txt"],
        stage="test",
        description="add hello",
    )
    assert commit is not None
    # Commit is recorded in log
    log = subprocess.run(
        ["git", "-C", str(proj), "log", "--oneline"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "add hello" in log.stdout


def test_new_workspace_can_commit_deck_vector(tmp_path: Path, guard: ToolGuard) -> None:
    """Issue #4: deck_vector.pptx must survive the blanket *.pptx exclusion."""
    proj = tmp_path / "proj"
    proj.mkdir()
    mgr = GitManager(project_dir=proj, guard=guard, verbose=False)
    mgr.initialize_repository()

    assert not _is_ignored(proj, "deck_vector.pptx")
    # Other decks stay whitelisted, unrelated .pptx files stay ignored.
    assert not _is_ignored(proj, "deck.pptx")
    assert _is_ignored(proj, "scratch.pptx")

    (proj / "deck_vector.pptx").write_bytes(b"PK\x03\x04stub")
    commit = mgr.commit(
        files=["deck_vector.pptx"],
        stage="assembly",
        description="add vector deck",
    )
    assert commit is not None
    tracked = subprocess.run(
        ["git", "-C", str(proj), "ls-files"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "deck_vector.pptx" in tracked.stdout.split()


def test_reconcile_repairs_old_workspace(tmp_path: Path, guard: ToolGuard) -> None:
    """An existing workspace with a pre-#4 .gitignore gets repaired in place."""
    proj = tmp_path / "old"
    proj.mkdir()
    mgr = GitManager(project_dir=proj, guard=guard, verbose=False)
    mgr.initialize_repository()

    # Roll the workspace back to the old template: no deck_vector whitelist.
    old_format = DEFAULT_GITIGNORE.replace("!deck_vector.pptx\n", "")
    assert "!deck_vector.pptx" not in old_format
    (proj / ".gitignore").write_text(old_format)
    assert _is_ignored(proj, "deck_vector.pptx")

    # Touching the existing workspace reconciles it.
    assert not mgr.initialize_repository()
    assert not _is_ignored(proj, "deck_vector.pptx")

    # Repair preserves the rest of the file rather than overwriting it.
    repaired = (proj / ".gitignore").read_text()
    assert "# Large binary outputs" in repaired
    assert _is_ignored(proj, "scratch.pptx")


def test_reconcile_is_idempotent(tmp_path: Path, guard: ToolGuard) -> None:
    proj = tmp_path / "proj"
    proj.mkdir()
    mgr = GitManager(project_dir=proj, guard=guard, verbose=False)
    mgr.initialize_repository()

    # Freshly written template needs no repair.
    assert mgr.reconcile_gitignore() == []

    (proj / ".gitignore").write_text(DEFAULT_GITIGNORE.replace("!deck_vector.pptx\n", ""))
    assert mgr.reconcile_gitignore() == ["!deck_vector.pptx"]

    after_first = (proj / ".gitignore").read_text()
    assert mgr.reconcile_gitignore() == []
    assert (proj / ".gitignore").read_text() == after_first


def test_reconcile_preserves_custom_entries(tmp_path: Path, guard: ToolGuard) -> None:
    """A workspace that added its own rules keeps them through a repair."""
    proj = tmp_path / "proj"
    proj.mkdir()
    mgr = GitManager(project_dir=proj, guard=guard, verbose=False)
    mgr.initialize_repository(gitignore_extra="# project-specific\nsecrets.env\n")

    (proj / ".gitignore").write_text(
        (proj / ".gitignore").read_text().replace("!deck_vector.pptx\n", "")
    )
    mgr.reconcile_gitignore()

    assert _is_ignored(proj, "secrets.env")
    assert not _is_ignored(proj, "deck_vector.pptx")


def test_reconcile_noop_without_gitignore(tmp_path: Path, guard: ToolGuard) -> None:
    proj = tmp_path / "proj"
    proj.mkdir()
    mgr = GitManager(project_dir=proj, guard=guard, verbose=False)
    assert mgr.reconcile_gitignore() == []
    assert not (proj / ".gitignore").exists()


def _broken_workspace(tmp_path: Path, guard: ToolGuard, name: str) -> GitManager:
    proj = tmp_path / name
    proj.mkdir()
    mgr = GitManager(project_dir=proj, guard=guard, verbose=False)
    mgr.initialize_repository()
    return mgr


def test_reconcile_survives_unreadable_gitignore(
    tmp_path: Path, guard: ToolGuard
) -> None:
    """A cosmetic .gitignore problem must not escalate into losing git tracking.

    initialize_repository() runs the repair, and callers upstream catch broad
    exceptions and drop the GitManager entirely — so a raise here would
    silently disable all commits for the run.
    """
    if os.geteuid() == 0:
        pytest.skip("root ignores file permissions")
    mgr = _broken_workspace(tmp_path, guard, "noperm")
    gitignore = mgr.project_dir / ".gitignore"
    gitignore.write_text(DEFAULT_GITIGNORE.replace("!deck_vector.pptx\n", ""))
    gitignore.chmod(0o000)
    try:
        assert mgr.reconcile_gitignore() == []
        # The whole init path stays non-raising.
        assert not mgr.initialize_repository()
    finally:
        gitignore.chmod(0o644)


def test_reconcile_survives_gitignore_directory(
    tmp_path: Path, guard: ToolGuard
) -> None:
    mgr = _broken_workspace(tmp_path, guard, "isdir")
    gitignore = mgr.project_dir / ".gitignore"
    gitignore.unlink()
    gitignore.mkdir()
    assert mgr.reconcile_gitignore() == []
    assert not mgr.initialize_repository()


def test_reconcile_survives_non_utf8_gitignore(
    tmp_path: Path, guard: ToolGuard
) -> None:
    mgr = _broken_workspace(tmp_path, guard, "binary")
    gitignore = mgr.project_dir / ".gitignore"
    gitignore.write_bytes(b"*.pptx\n\xff\xfe\x00invalid\n")
    assert mgr.reconcile_gitignore() == []
    assert not mgr.initialize_repository()


def test_reconcile_failure_is_warned(
    tmp_path: Path, guard: ToolGuard, caplog: pytest.LogCaptureFixture
) -> None:
    """Skipping the repair must be visible, not silent."""
    mgr = _broken_workspace(tmp_path, guard, "warned")
    gitignore = mgr.project_dir / ".gitignore"
    gitignore.write_bytes(b"\xff\xfe\x00invalid\n")
    with caplog.at_level(logging.WARNING, logger="wizard_core.git_manager"):
        mgr.reconcile_gitignore()
    assert any(r.levelno == logging.WARNING for r in caplog.records)
    assert "deck_vector.pptx" in caplog.text


def test_default_whitelist_lines_matches_template() -> None:
    lines = default_whitelist_lines()
    assert "!deck_vector.pptx" in lines
    assert all(line.startswith("!") for line in lines)
    assert len(lines) == DEFAULT_GITIGNORE.count("\n!")
