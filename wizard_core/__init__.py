"""wizard-core: shared infrastructure for document-generation wizards.

These tools (slide-wizard, proposal-wizard, repo-research-writer) run as
Claude Code skills — Claude itself is the LLM runtime. wizard-core
provides the deterministic infrastructure those tools all need: workflow
state, per-output-project git management, future shared parsers and
validators. There is no LLM client here — content generation happens
inside Claude Code, not via the Anthropic SDK.
"""

__version__ = "0.1.0"

from wizard_core.state_manager import StateManager, WorkflowSpec
from wizard_core.git_manager import GitManager, GitSafetyError, ToolGuard

__all__ = [
    "StateManager",
    "WorkflowSpec",
    "GitManager",
    "GitSafetyError",
    "ToolGuard",
]
