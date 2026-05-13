"""Tests for the revision-loop tracking promoted from rrwrite into wizard-core."""

from __future__ import annotations

from pathlib import Path

import pytest

from wizard_core.state_manager import StateManager, WorkflowSpec


@pytest.fixture
def spec() -> WorkflowSpec:
    # 'revision' must be present in stages for revision tracking to work.
    return WorkflowSpec(
        tool_name="testtool",
        state_dir_name=".testtool",
        stages=["draft", "critique", "revision"],
        guard=None,
    )


@pytest.fixture
def mgr(tmp_path: Path, spec: WorkflowSpec) -> StateManager:
    return StateManager(output_dir=tmp_path / "proj", spec=spec, enable_git=False)


def test_start_revision_initializes_shape(mgr: StateManager) -> None:
    mgr.start_revision(max_iterations=3, min_improvement=0.25)
    rev = mgr.state["workflow_status"]["revision"]
    assert rev["status"] == "in_progress"
    assert rev["data"]["max_iterations"] == 3
    assert rev["data"]["min_improvement"] == 0.25
    assert rev["data"]["iterations"] == []
    assert rev["data"]["current_iteration"] == 0


def test_start_revision_without_stage_raises(tmp_path: Path) -> None:
    spec = WorkflowSpec(
        tool_name="nospec",
        state_dir_name=".nospec",
        stages=["draft"],  # no 'revision'
        guard=None,
    )
    mgr = StateManager(output_dir=tmp_path / "proj", spec=spec, enable_git=False)
    with pytest.raises(ValueError, match="'revision' stage missing"):
        mgr.start_revision(max_iterations=3)


def test_record_iteration_computes_improvement_rate(mgr: StateManager) -> None:
    mgr.start_revision(max_iterations=3)
    record = mgr.record_iteration(
        iteration=1,
        sections_revised=["04_motivation", "07_results"],
        metrics_before={"major": 5, "minor": 12},
        metrics_after={"major": 2, "minor": 9},
        critique_files={"before": "critique_v1.md", "after": "critique_v2.md"},
    )
    assert record["iteration"] == 1
    assert record["sections_revised"] == ["04_motivation", "07_results"]
    assert record["issues_before"] == {"major": 5, "minor": 12}
    assert record["issues_after"] == {"major": 2, "minor": 9}
    assert record["convergence_metrics"]["major_resolved"] == 3
    assert record["convergence_metrics"]["minor_resolved"] == 3
    assert record["convergence_metrics"]["improvement_rate"] == pytest.approx(0.6)
    assert mgr.state["workflow_status"]["revision"]["data"]["current_iteration"] == 1


def test_record_iteration_with_zero_majors_before_is_zero_rate(mgr: StateManager) -> None:
    mgr.start_revision(max_iterations=3)
    record = mgr.record_iteration(
        iteration=1,
        sections_revised=[],
        metrics_before={"major": 0, "minor": 5},
        metrics_after={"major": 0, "minor": 5},
    )
    assert record["convergence_metrics"]["improvement_rate"] == 0.0


def test_check_convergence_major_resolved() -> None:
    stop, reason = StateManager.check_convergence(
        metrics_after={"major": 0, "minor": 4},
        iteration=2,
        max_iterations=5,
        improvement_rate=0.8,
    )
    assert stop is True
    assert reason == "major_issues_resolved"


def test_check_convergence_max_iterations() -> None:
    stop, reason = StateManager.check_convergence(
        metrics_after={"major": 1, "minor": 3},
        iteration=3,
        max_iterations=3,
        improvement_rate=0.5,
    )
    assert stop is True
    assert reason == "max_iterations_reached"


def test_check_convergence_stalled() -> None:
    stop, reason = StateManager.check_convergence(
        metrics_after={"major": 3, "minor": 7},
        iteration=2,
        max_iterations=5,
        improvement_rate=0.05,
        min_improvement=0.2,
    )
    assert stop is True
    assert reason == "stalled_no_improvement"


def test_check_convergence_continues() -> None:
    stop, reason = StateManager.check_convergence(
        metrics_after={"major": 2, "minor": 6},
        iteration=1,
        max_iterations=3,
        improvement_rate=0.6,
    )
    assert stop is False
    assert reason is None


def test_complete_revision_marks_done_and_stores_verdict(mgr: StateManager) -> None:
    mgr.start_revision(max_iterations=3)
    mgr.record_iteration(
        iteration=1,
        sections_revised=["04_x"],
        metrics_before={"major": 4, "minor": 8},
        metrics_after={"major": 0, "minor": 5},
    )
    mgr.complete_revision(
        convergence_status="converged",
        convergence_reason="major_issues_resolved",
    )
    slot = mgr.state["workflow_status"]["revision"]
    assert slot["status"] == "completed"
    assert slot["completed_at"] is not None
    assert slot["data"]["convergence_status"] == "converged"
    assert slot["data"]["convergence_reason"] == "major_issues_resolved"


def test_get_revision_summary_before_start(mgr: StateManager) -> None:
    summary = mgr.get_revision_summary()
    assert summary["status"] == "not_started"


def test_get_revision_summary_after_iterations(mgr: StateManager) -> None:
    mgr.start_revision(max_iterations=3)
    mgr.record_iteration(
        iteration=1, sections_revised=["04_a"],
        metrics_before={"major": 5, "minor": 12},
        metrics_after={"major": 2, "minor": 9},
    )
    mgr.record_iteration(
        iteration=2, sections_revised=["05_b"],
        metrics_before={"major": 2, "minor": 9},
        metrics_after={"major": 0, "minor": 6},
    )
    mgr.complete_revision("converged", "major_issues_resolved")

    s = mgr.get_revision_summary()
    assert s["status"] == "completed"
    assert s["iterations_run"] == 2
    assert s["max_iterations"] == 3
    assert s["current_iteration"] == 2
    assert s["convergence_status"] == "converged"
    assert s["convergence_reason"] == "major_issues_resolved"
    assert s["issues_initial"] == {"major": 5, "minor": 12}
    assert s["issues_final"] == {"major": 0, "minor": 6}
    assert s["total_major_resolved"] == 5
    assert s["total_minor_resolved"] == 6


def test_revision_persists_across_instances(tmp_path: Path, spec: WorkflowSpec) -> None:
    out = tmp_path / "persist"
    a = StateManager(output_dir=out, spec=spec, enable_git=False)
    a.start_revision(max_iterations=4)
    a.record_iteration(
        iteration=1, sections_revised=["x"],
        metrics_before={"major": 3, "minor": 5},
        metrics_after={"major": 1, "minor": 3},
    )

    b = StateManager(output_dir=out, spec=spec, enable_git=False)
    rev = b.state["workflow_status"]["revision"]
    assert rev["status"] == "in_progress"
    assert len(rev["data"]["iterations"]) == 1
    assert rev["data"]["current_iteration"] == 1
