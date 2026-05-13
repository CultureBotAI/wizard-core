"""Smoke tests for GitManager safety and basic flow."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from wizard_core.git_manager import GitManager, GitSafetyError, ToolGuard


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
