"""Per-output-project git management with safety guards.

Each output project (a deck, a manuscript, a proposal) lives in its own git
repository, separate from the wizard tool that produced it. This module
provides safe initialization, .gitignore creation, and structured commits,
plus guard rails preventing accidental commits into the tool repository
itself.

Genericized from `repo-research-writer/scripts/rrwrite_git.py`.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


class GitSafetyError(Exception):
    """Raised when a git operation would be unsafe."""


@dataclass(frozen=True)
class ToolGuard:
    """Markers identifying the wizard tool repo that must not receive commits.

    A ToolGuard describes the *tool* (e.g., slide-wizard) so the GitManager,
    which operates on *output* projects (decks, manuscripts, proposals), can
    refuse to operate when pointed at a directory that looks like the tool
    repo itself.
    """

    tool_name: str
    state_dir_name: str  # e.g., ".swiz", ".rrwrite", ".pwiz"
    tool_repo_markers: Sequence[str] = field(default_factory=tuple)
    remote_url_patterns: Sequence[str] = field(default_factory=tuple)


DEFAULT_GITIGNORE = """# Large binary outputs
*.pdf
*.docx
*.doc
*.pptx

# …but assembled deliverables should travel with the project repo.
# Each tool's assembler writes to one of these well-known filenames.
!deck.pdf
!deck.html
!deck.pptx
!deck_editable.pptx
!deck_vector.pptx
!manuscript.pdf
!manuscript.docx
!full_manuscript.pdf
!full_manuscript.docx
!proposal.pdf
!proposal.docx

# Temporary caches
__pycache__/
.cache/
.tmp/

# OS files
.DS_Store
Thumbs.db
._*

# Editor files
*.swp
*.swo
*~
.vscode/
.idea/

# Build artifacts
build/
dist/
*.egg-info/
"""

RECONCILE_MARKER = (
    "# Added by wizard-core: deliverables whitelisted after this repo was created."
)


def default_whitelist_lines() -> List[str]:
    """The `!`-prefixed deliverable exceptions in the default .gitignore.

    Derived from DEFAULT_GITIGNORE rather than duplicated, so the repair path
    below cannot drift from the template.
    """
    return [
        line.strip()
        for line in DEFAULT_GITIGNORE.splitlines()
        if line.strip().startswith("!")
    ]


class GitManager:
    """Manage git operations for an output project with safety guarantees.

    The output project is the workspace produced *by* the wizard (a deck, a
    manuscript, a proposal). It is NOT the tool repo. GitManager refuses to
    operate if the directory it's pointed at looks like the tool repo itself.
    """

    def __init__(
        self,
        project_dir: Path,
        guard: ToolGuard,
        auto_commit: bool = True,
        verbose: bool = True,
        commit_author_tag: Optional[str] = None,
    ):
        """
        Args:
            project_dir: Path to the output project (must not be the tool repo).
            guard: ToolGuard describing the tool that must not be committed to.
            auto_commit: Enable automatic commits after stages.
            verbose: Emit informational messages.
            commit_author_tag: String prepended to commit messages
                (defaults to f"[{guard.tool_name}]").
        """
        self.project_dir = Path(project_dir).resolve()
        self.guard = guard
        self.auto_commit = auto_commit
        self.verbose = verbose
        self.commit_author_tag = commit_author_tag or f"[{guard.tool_name}]"
        self.logger = logging.getLogger(__name__)

        self._validate_project_directory()
        self._refuse_if_tool_repo()

        self.git_dir = self.project_dir / ".git"

    # ----- safety checks -----

    def _validate_project_directory(self) -> None:
        if not self.project_dir.exists():
            raise GitSafetyError(
                f"Project directory does not exist: {self.project_dir}"
            )

    def _refuse_if_tool_repo(self) -> None:
        for marker in self.guard.tool_repo_markers:
            if (self.project_dir / marker).exists():
                raise GitSafetyError(
                    f"\n{'=' * 70}\n"
                    f"SAFETY VIOLATION: {self.guard.tool_name.upper()} TOOL REPOSITORY DETECTED\n"
                    f"{'=' * 70}\n"
                    f"Directory: {self.project_dir}\n"
                    f"This appears to be the {self.guard.tool_name} tool repository,\n"
                    f"not an output workspace. Refusing to initialize git here.\n"
                    f"{'=' * 70}\n"
                )
        if self.verbose:
            self.logger.debug("Tool-repo safety check passed: %s", self.project_dir)

    def _check_remote_url(self) -> None:
        if not self.git_dir.exists():
            return
        try:
            result = subprocess.run(
                ["git", f"--git-dir={self.git_dir}", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            return
        if result.returncode != 0:
            return
        remote_url = result.stdout.strip().lower()
        for pattern in self.guard.remote_url_patterns:
            if pattern.lower() in remote_url:
                raise GitSafetyError(
                    f"\n{'=' * 70}\n"
                    f"SAFETY VIOLATION: {self.guard.tool_name.upper()} TOOL REMOTE DETECTED\n"
                    f"{'=' * 70}\n"
                    f"Git directory: {self.git_dir}\n"
                    f"Remote URL: {remote_url}\n"
                    f"Refusing to commit — this would push output content\n"
                    f"into the {self.guard.tool_name} tool repository.\n"
                    f"{'=' * 70}\n"
                )

    # ----- repository ops -----

    def initialize_repository(self, gitignore_extra: str = "") -> bool:
        """Initialize a git repository in the project directory.

        Returns True on first init, False if already initialized.
        """
        if self.git_dir.exists():
            if self.verbose:
                self.logger.info("Git already initialized: %s", self.project_dir)
            self._check_remote_url()
            self.reconcile_gitignore()
            return False

        self.project_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "init", str(self.project_dir)],
            check=True,
            capture_output=True,
        )
        if self.verbose:
            self.logger.info("Git initialized: %s", self.project_dir)

        self._write_gitignore(gitignore_extra)
        self._install_safety_hook()
        self._git_add([".gitignore"])
        self.commit(
            files=[".gitignore"],
            stage="initialization",
            description=f"Initialize {self.guard.tool_name} output repository",
            metadata={"managed_by": self.guard.tool_name},
        )
        return True

    def _write_gitignore(self, extra: str = "") -> None:
        content = DEFAULT_GITIGNORE
        if extra:
            content = content + "\n" + extra
        (self.project_dir / ".gitignore").write_text(content)

    def reconcile_gitignore(self) -> List[str]:
        """Append deliverable whitelist entries missing from an existing .gitignore.

        Workspaces created before a deliverable filename was whitelisted keep
        the old .gitignore on disk, so `git add` on that artifact fails and the
        file is never committed (issue #4: deck_vector.pptx). Appending is
        correct for negation patterns — the last matching rule wins, so these
        land after the `*.pptx` exclusion they need to override.

        Idempotent. Returns the lines added, empty if already up to date. The
        reconciled file is left unstaged; the ignore rules take effect from the
        working tree immediately.
        """
        gitignore = self.project_dir / ".gitignore"
        if not gitignore.exists():
            return []

        content = gitignore.read_text()
        present = {line.strip() for line in content.splitlines()}
        missing = [line for line in default_whitelist_lines() if line not in present]
        if not missing:
            return []

        if not content.endswith("\n"):
            content += "\n"
        content += "\n" + RECONCILE_MARKER + "\n" + "\n".join(missing) + "\n"
        gitignore.write_text(content)
        if self.verbose:
            self.logger.info(
                "Reconciled .gitignore in %s: added %s",
                self.project_dir,
                ", ".join(missing),
            )
        return missing

    def _install_safety_hook(self) -> None:
        hooks_dir = self.git_dir / "hooks"
        hooks_dir.mkdir(exist_ok=True)
        hook = hooks_dir / "pre-commit"
        hook.write_text(
            "#!/bin/bash\n"
            "# wizard-core safety hook\n"
            "if git diff --cached --name-only | grep -q '\\.git/'; then\n"
            '    echo "WARNING: committing .git/ contents — unusual." >&2\n'
            "fi\n"
            "exit 0\n"
        )
        hook.chmod(0o755)

    def _git_add(self, files: Sequence[str]) -> None:
        self._check_remote_url()
        subprocess.run(
            [
                "git",
                f"--git-dir={self.git_dir}",
                f"--work-tree={self.project_dir}",
                "add",
                *files,
            ],
            cwd=self.project_dir,
            check=True,
            capture_output=True,
        )

    def commit(
        self,
        files: Sequence[str],
        stage: str,
        description: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Stage and commit files with a structured message.

        Returns the commit hash, or None if auto_commit is disabled.
        """
        if not self.auto_commit:
            return None
        if not self.git_dir.exists():
            raise GitSafetyError(
                f"Git repository not initialized in {self.project_dir}. "
                f"Call initialize_repository() first."
            )
        self._check_remote_url()
        self._git_add(files)

        msg_lines = [
            f"{self.commit_author_tag} {stage}: {description}",
            "",
            f"Stage: {stage}",
        ]
        for k, v in (metadata or {}).items():
            msg_lines.append(f"{k}: {v}")
        msg_lines.append(f"Timestamp: {datetime.now().isoformat()}")

        subprocess.run(
            [
                "git",
                f"--git-dir={self.git_dir}",
                f"--work-tree={self.project_dir}",
                "commit",
                "-m",
                "\n".join(msg_lines),
            ],
            cwd=self.project_dir,
            check=True,
            capture_output=True,
        )
        commit = self.get_current_commit()
        if self.verbose and commit:
            self.logger.info("Committed %s: %s", commit[:7], description)
        return commit

    def get_current_commit(self) -> Optional[str]:
        if not self.git_dir.exists():
            return None
        try:
            result = subprocess.run(
                ["git", f"--git-dir={self.git_dir}", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None

    def get_status(self) -> str:
        if not self.git_dir.exists():
            return "Not a git repository"
        result = subprocess.run(
            [
                "git",
                f"--git-dir={self.git_dir}",
                f"--work-tree={self.project_dir}",
                "status",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout


def install_tool_repo_protection(tool_repo_path: Path, output_dir_name: str) -> Path:
    """Install a pre-commit hook in the tool repo that rejects output-project files.

    Mirrors the protection rrwrite installs against committing manuscript/
    content into the rrwrite tool repo. Returns the hook path written.
    """
    git_dir = tool_repo_path / ".git"
    if not git_dir.exists():
        raise FileNotFoundError(f"Tool repo is not a git repository: {tool_repo_path}")
    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)
    hook = hooks_dir / "pre-commit"
    hook.write_text(
        "#!/bin/bash\n"
        "# wizard-core tool-repo protection hook\n"
        f'protected="^{output_dir_name}/"\n'
        'offending=$(git diff --cached --name-only | grep -E "$protected" || true)\n'
        'if [ -n "$offending" ]; then\n'
        '    echo "COMMIT REJECTED: output-project files detected" >&2\n'
        '    echo "$offending" >&2\n'
        '    echo "Commit these inside the output project repo instead." >&2\n'
        "    exit 1\n"
        "fi\n"
        "exit 0\n"
    )
    hook.chmod(0o755)
    return hook
