"""Smoke tests for the generic StateManager."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wizard_core.state_manager import StateManager, WorkflowSpec


@pytest.fixture
def spec() -> WorkflowSpec:
    return WorkflowSpec(
        tool_name="testtool",
        state_dir_name=".testtool",
        stages=["analyze", "plan", "draft", "assemble"],
        guard=None,
    )


def test_creates_initial_state(tmp_path: Path, spec: WorkflowSpec) -> None:
    manager = StateManager(output_dir=tmp_path / "proj", spec=spec, enable_git=False)
    state_file = tmp_path / "proj" / ".testtool" / "state.json"
    assert state_file.exists()
    data = json.loads(state_file.read_text())
    assert data["tool"] == "testtool"
    assert set(data["workflow_status"].keys()) == {"analyze", "plan", "draft", "assemble"}
    assert all(v["status"] == "not_started" for v in data["workflow_status"].values())
    assert manager.get_current_stage() == "analyze"


def test_update_stage_and_progress(tmp_path: Path, spec: WorkflowSpec) -> None:
    manager = StateManager(output_dir=tmp_path / "proj", spec=spec, enable_git=False)
    manager.update_stage("analyze", status="completed", file="analysis.md", note="ok")
    manager.update_stage("plan", status="in_progress")

    assert manager.is_stage_completed("analyze")
    assert manager.get_stage_data("analyze") == {"note": "ok"}
    assert manager.get_current_stage() == "plan"

    progress = manager.get_progress_summary()
    assert progress["completed_stages"] == 1
    assert progress["total_stages"] == 4
    assert progress["progress_percentage"] == pytest.approx(25.0)


def test_persists_across_instances(tmp_path: Path, spec: WorkflowSpec) -> None:
    out = tmp_path / "proj"
    StateManager(output_dir=out, spec=spec, enable_git=False).update_stage(
        "analyze", status="completed", file="a.md"
    )
    reloaded = StateManager(output_dir=out, spec=spec, enable_git=False)
    assert reloaded.is_stage_completed("analyze")
    assert reloaded.state["workflow_status"]["analyze"]["file"] == "a.md"


def test_unknown_stage_raises(tmp_path: Path, spec: WorkflowSpec) -> None:
    manager = StateManager(output_dir=tmp_path / "proj", spec=spec, enable_git=False)
    with pytest.raises(ValueError):
        manager.update_stage("nonexistent", status="completed")
