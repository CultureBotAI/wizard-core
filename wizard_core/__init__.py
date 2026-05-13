"""wizard-core: shared infrastructure for document-generation wizards.

These tools (slide-wizard, proposal-wizard, repo-research-writer) run as
Claude Code skills — Claude itself is the LLM runtime. wizard-core
provides the deterministic infrastructure those tools all need: workflow
state, per-output-project git management, Google API access for shared
service-account credentials, document parsers, citation validation,
literature search, manifest generation, and an evidence tracker. There is
no LLM client here — content generation happens inside Claude Code, not
via the Anthropic SDK.
"""

__version__ = "0.2.0"

from wizard_core.state_manager import StateManager, WorkflowSpec
from wizard_core.git_manager import GitManager, GitSafetyError, ToolGuard

__all__ = [
    "StateManager",
    "WorkflowSpec",
    "GitManager",
    "GitSafetyError",
    "ToolGuard",
]

# Document parsing — optional extras (PyPDF2 / python-docx / bs4)
try:
    from wizard_core.document_parsers import (
        BaseDocumentParser,
        PDFParser,
        DOCXParser,
        HTMLParser,
        YAMLConverter,
        ParsingError,
        create_parser,
    )
    __all__ += [
        "BaseDocumentParser",
        "PDFParser",
        "DOCXParser",
        "HTMLParser",
        "YAMLConverter",
        "ParsingError",
        "create_parser",
    ]
except ImportError:
    pass

# Citation validation — always available (uses stdlib only)
from wizard_core.citation_validator import (
    CitationError,
    CitationNotFoundError,
    CitationMismatchError,
    CitationEntryValidator,
    CitationBusinessValidator,
    CitationAssemblyValidator,
    CitationAuditor,
    PaperpileCitationHandler,
    validate_all_layers,
)
__all__ += [
    "CitationError",
    "CitationNotFoundError",
    "CitationMismatchError",
    "CitationEntryValidator",
    "CitationBusinessValidator",
    "CitationAssemblyValidator",
    "CitationAuditor",
    "PaperpileCitationHandler",
    "validate_all_layers",
]

# Manifest generation — stdlib only; jsonschema optional for validation
from wizard_core.manifest_generator import ManifestGenerator, ManifestValidator
__all__ += ["ManifestGenerator", "ManifestValidator"]

# Schema builder — stdlib only
from wizard_core.schema_builder import SchemaBuilder, SchemaBuilderError
__all__ += ["SchemaBuilder", "SchemaBuilderError"]

# Literature search — pluggable backends; requests-cache optional
from wizard_core.literature_search import (
    search_literature,
    deduplicate_papers,
    setup_cache,
)
__all__ += ["search_literature", "deduplicate_papers", "setup_cache"]

# Evidence tracking — stdlib only
from wizard_core.evidence_tracker import EvidenceTracker
__all__ += ["EvidenceTracker"]

# GoogleClient is an optional import (requires wizard-core[google]).
try:
    from wizard_core.google_client import (
        GoogleClient,
        GoogleCredentialsNotFoundError,
        EXPECTED_CLIENT_EMAIL,
        locate_credentials,
    )
    __all__ += [
        "GoogleClient",
        "GoogleCredentialsNotFoundError",
        "EXPECTED_CLIENT_EMAIL",
        "locate_credentials",
    ]
except ImportError:
    pass
