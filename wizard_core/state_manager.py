"""Generic workflow state machine for wizard tools.

Each wizard tool (slide-wizard, proposal-wizard, repo-research-writer)
defines a list of workflow stages. StateManager persists per-stage status,
file references, timestamps, and (optional) git commit hashes to
`{output_dir}/{state_dir_name}/state.json`.

Genericized from `repo-research-writer/scripts/rrwrite_state_manager.py`
and `proposal-wizard/scripts/pwiz_state_manager.py`. The original
manuscript- and proposal-specific helpers (update_assessment_stage,
update_research_with_import, etc.) are intentionally not ported here —
each tool can wrap StateManager with its own domain-specific helpers.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from wizard_core.git_manager import GitManager, GitSafetyError, ToolGuard


@dataclass(frozen=True)
class WorkflowSpec:
    """Per-tool workflow definition consumed by StateManager.

    Attributes:
        tool_name: Short name used in commit messages and logs ("swiz", "rrwrite", "pwiz").
        state_dir_name: Hidden directory under output_dir holding state.json (".swiz" etc.).
        stages: Ordered list of stage names this tool moves through.
        guard: Tool-repo safety guard for GitManager (omit for git-disabled use).
    """

    tool_name: str
    state_dir_name: str
    stages: Sequence[str]
    guard: Optional[ToolGuard] = None


_STATE_VERSION = "1.0"


class StateManager:
    """Persistent per-output-project workflow state, with optional git tracking."""

    def __init__(
        self,
        output_dir: str | Path,
        spec: WorkflowSpec,
        enable_git: bool = True,
        auto_commit: bool = True,
    ):
        self.spec = spec
        self.output_dir = Path(output_dir).resolve()
        self.state_dir = self.output_dir / spec.state_dir_name
        self.state_file = self.state_dir / "state.json"
        self.logger = logging.getLogger(__name__)

        self._init_state()

        self.git_manager: Optional[GitManager] = None
        if enable_git and spec.guard is not None:
            self._init_git(auto_commit=auto_commit)
        elif enable_git and spec.guard is None:
            self.logger.debug(
                "Git enabled but no ToolGuard provided in WorkflowSpec; skipping git."
            )

    # ----- state I/O -----

    def _init_state(self) -> None:
        if not self.state_file.exists():
            self.state: Dict[str, Any] = self._create_initial_state()
            self._save_state()
        else:
            self._load_state()

    def _create_initial_state(self) -> Dict[str, Any]:
        now = self._now()
        return {
            "version": _STATE_VERSION,
            "tool": self.spec.tool_name,
            "created_at": now,
            "last_updated": now,
            "output_dir": str(self.output_dir),
            "workflow_status": {
                stage: {
                    "status": "not_started",
                    "file": None,
                    "completed_at": None,
                    "git_commit": None,
                    "data": {},
                }
                for stage in self.spec.stages
            },
            "files": {},
            "metadata": {},
        }

    def _load_state(self) -> None:
        with self.state_file.open("r") as f:
            self.state = json.load(f)
        # Backfill new stages added after first init.
        wf = self.state.setdefault("workflow_status", {})
        for stage in self.spec.stages:
            wf.setdefault(
                stage,
                {
                    "status": "not_started",
                    "file": None,
                    "completed_at": None,
                    "git_commit": None,
                    "data": {},
                },
            )

    def _save_state(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state["last_updated"] = self._now()
        with self.state_file.open("w") as f:
            json.dump(self.state, f, indent=2)

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat()

    # ----- git -----

    def _init_git(self, auto_commit: bool) -> None:
        try:
            self.git_manager = GitManager(
                project_dir=self.output_dir,
                guard=self.spec.guard,
                auto_commit=auto_commit,
            )
            initialized = self.git_manager.initialize_repository()
            self.state.setdefault("git", {})
            self.state["git"]["repository_initialized"] = True
            if initialized:
                self.state["git"]["initialized_at"] = self._now()
            self._save_state()
        except GitSafetyError as e:
            self.logger.error("Git initialization failed (safety): %s", e)
            self.git_manager = None
        except Exception as e:  # pragma: no cover - defensive
            self.logger.warning("Git initialization failed: %s", e)
            self.git_manager = None

    def _get_git_commit_short(self) -> Optional[str]:
        if not self.git_manager:
            return None
        commit = self.git_manager.get_current_commit()
        return commit[:7] if commit else None

    def commit_stage(
        self,
        stage: str,
        files: Sequence[str],
        description: str,
        **metadata: Any,
    ) -> Optional[str]:
        if not self.git_manager:
            return None
        try:
            return self.git_manager.commit(
                files=list(files),
                stage=stage,
                description=description,
                metadata=metadata,
            )
        except GitSafetyError as e:
            self.logger.error("Commit failed (safety): %s", e)
        except Exception as e:
            self.logger.warning("Commit failed: %s", e)
        return None

    # ----- stage updates -----

    def update_stage(
        self,
        stage: str,
        status: str,
        file: Optional[str] = None,
        **data: Any,
    ) -> None:
        """Update a stage's status, optional file pointer, and arbitrary data."""
        if stage not in self.state["workflow_status"]:
            raise ValueError(f"Unknown stage for {self.spec.tool_name}: {stage}")
        slot = self.state["workflow_status"][stage]
        slot["status"] = status
        if file is not None:
            slot["file"] = file
        if data:
            slot.setdefault("data", {}).update(data)
        if status == "completed":
            slot["completed_at"] = self._now()
            slot["git_commit"] = self._get_git_commit_short()
        self._save_state()

    def set_file(self, key: str, path: str) -> None:
        self.state.setdefault("files", {})[key] = path
        self._save_state()

    def set_metadata(self, **kwargs: Any) -> None:
        self.state.setdefault("metadata", {}).update(kwargs)
        self._save_state()

    # ----- queries -----

    def get_stage_status(self, stage: str) -> str:
        return self.state["workflow_status"].get(stage, {}).get("status", "not_started")

    def is_stage_completed(self, stage: str) -> bool:
        return self.get_stage_status(stage) == "completed"

    def get_stage_data(self, stage: str) -> Dict[str, Any]:
        return self.state["workflow_status"].get(stage, {}).get("data", {})

    def get_current_stage(self) -> str:
        for stage in self.spec.stages:
            status = self.get_stage_status(stage)
            if status in ("not_started", "in_progress"):
                return stage
        return "completed"

    def get_progress_summary(self) -> Dict[str, Any]:
        total = len(self.spec.stages)
        completed = sum(1 for s in self.spec.stages if self.is_stage_completed(s))
        return {
            "tool": self.spec.tool_name,
            "total_stages": total,
            "completed_stages": completed,
            "current_stage": self.get_current_stage(),
            "progress_percentage": (completed / total * 100) if total else 0.0,
        }

    # ----- revision-loop tracking -----
    #
    # Generic critique → revise → re-critique iteration tracking. Tools that
    # want to use this must include "revision" in their WorkflowSpec.stages.
    # Iteration records live under state["workflow_status"]["revision"]["data"].
    # Pattern promoted from `repo-research-writer/scripts/rrwrite_state_manager.py`
    # so slide-wizard, proposal-wizard, and rrwrite share one implementation.

    def _require_revision_stage(self) -> None:
        if "revision" not in self.state["workflow_status"]:
            raise ValueError(
                f"'revision' stage missing from WorkflowSpec for "
                f"{self.spec.tool_name!r}. Add 'revision' to your spec's "
                f"stages to use revision tracking."
            )

    def start_revision(
        self,
        max_iterations: int,
        min_improvement: float = 0.2,
    ) -> None:
        """Initialize revision tracking under the 'revision' workflow stage."""
        self._require_revision_stage()
        slot = self.state["workflow_status"]["revision"]
        slot["status"] = "in_progress"
        slot["data"] = {
            "max_iterations": max_iterations,
            "min_improvement": min_improvement,
            "current_iteration": 0,
            "iterations": [],
            "convergence_status": None,
            "convergence_reason": None,
        }
        self._save_state()

    def record_iteration(
        self,
        iteration: int,
        sections_revised: Sequence[str],
        metrics_before: Dict[str, int],
        metrics_after: Dict[str, int],
        critique_files: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Append one revision iteration with convergence metrics; return the record."""
        self._require_revision_stage()
        rev = self.state["workflow_status"]["revision"].setdefault("data", {})
        rev.setdefault("iterations", [])

        major_before = int(metrics_before.get("major", 0))
        major_after = int(metrics_after.get("major", 0))
        minor_before = int(metrics_before.get("minor", 0))
        minor_after = int(metrics_after.get("minor", 0))

        major_resolved = major_before - major_after
        minor_resolved = minor_before - minor_after
        improvement_rate = (
            major_resolved / major_before if major_before > 0 else 0.0
        )

        record = {
            "iteration": iteration,
            "sections_revised": list(sections_revised),
            "issues_before": {"major": major_before, "minor": minor_before},
            "issues_after": {"major": major_after, "minor": minor_after},
            "convergence_metrics": {
                "major_resolved": major_resolved,
                "minor_resolved": minor_resolved,
                "improvement_rate": improvement_rate,
            },
            "critique_files": critique_files or {},
            "git_commit": self._get_git_commit_short(),
            "timestamp": self._now(),
        }
        rev["iterations"].append(record)
        rev["current_iteration"] = iteration
        self._save_state()
        return record

    @staticmethod
    def check_convergence(
        metrics_after: Dict[str, int],
        iteration: int,
        max_iterations: int,
        improvement_rate: float,
        min_improvement: float = 0.2,
    ) -> tuple:
        """Decide whether the revision loop should stop.

        Returns (should_stop, reason) where reason is one of
        'major_issues_resolved', 'max_iterations_reached',
        'stalled_no_improvement', or None when the loop should continue.
        """
        if int(metrics_after.get("major", 0)) == 0:
            return True, "major_issues_resolved"
        if iteration >= max_iterations:
            return True, "max_iterations_reached"
        if improvement_rate < min_improvement:
            return True, "stalled_no_improvement"
        return False, None

    def complete_revision(
        self,
        convergence_status: str,
        convergence_reason: str,
    ) -> None:
        """Mark revision tracking completed with a convergence verdict."""
        self._require_revision_stage()
        slot = self.state["workflow_status"]["revision"]
        slot["status"] = "completed"
        slot["completed_at"] = self._now()
        slot["git_commit"] = self._get_git_commit_short()
        data = slot.setdefault("data", {})
        data["convergence_status"] = convergence_status
        data["convergence_reason"] = convergence_reason
        self._save_state()

    def get_revision_summary(self) -> Dict[str, Any]:
        """Compact summary suitable for status output."""
        if "revision" not in self.state["workflow_status"]:
            return {"status": "not_applicable"}
        slot = self.state["workflow_status"]["revision"]
        if slot["status"] == "not_started":
            return {"status": "not_started"}
        data = slot.get("data", {})
        iterations = data.get("iterations", [])
        summary: Dict[str, Any] = {
            "status": slot["status"],
            "iterations_run": len(iterations),
            "max_iterations": data.get("max_iterations"),
            "current_iteration": data.get("current_iteration", 0),
            "convergence_status": data.get("convergence_status"),
            "convergence_reason": data.get("convergence_reason"),
        }
        if iterations:
            first = iterations[0]
            last = iterations[-1]
            summary["issues_initial"] = first["issues_before"]
            summary["issues_final"] = last["issues_after"]
            summary["total_major_resolved"] = (
                first["issues_before"]["major"] - last["issues_after"]["major"]
            )
            summary["total_minor_resolved"] = (
                first["issues_before"]["minor"] - last["issues_after"]["minor"]
            )
        return summary

    def export_state(self) -> Dict[str, Any]:
        return json.loads(json.dumps(self.state))

    def print_summary(self) -> None:
        progress = self.get_progress_summary()
        print()
        print("=" * 60)
        print(f"{self.spec.tool_name} workflow state")
        print("=" * 60)
        print(f"Output dir: {self.output_dir}")
        print(f"Last updated: {self.state.get('last_updated')}")
        print(
            f"Progress: {progress['completed_stages']}/{progress['total_stages']} "
            f"({progress['progress_percentage']:.0f}%)  current={progress['current_stage']}"
        )
        print("Stages:")
        for stage in self.spec.stages:
            slot = self.state["workflow_status"][stage]
            print(f"  - {stage}: {slot['status']}")
        print("=" * 60)
