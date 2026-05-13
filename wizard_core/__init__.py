"""wizard-core: shared infrastructure for document-generation wizards."""

__version__ = "0.1.0"

from wizard_core.state_manager import StateManager, WorkflowSpec
from wizard_core.git_manager import GitManager, GitSafetyError
from wizard_core.llm_client import LLMClient

__all__ = [
    "StateManager",
    "WorkflowSpec",
    "GitManager",
    "GitSafetyError",
    "LLMClient",
]
