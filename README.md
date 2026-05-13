# wizard-core

Shared infrastructure for the CultureBotAI document-generation wizards: [slide-wizard](https://github.com/CultureBotAI/slide-wizard), [proposal-wizard](https://github.com/CultureBotAI/proposal-wizard), and [repo-research-writer](https://github.com/CultureBotAI/repo-research-writer).

These wizards run as **Claude Code skills** — Claude itself is the LLM runtime. wizard-core provides only the deterministic infrastructure the wizards all need: workflow state, per-output-project git management, and (Phase 5) shared document parsers and validators. There is no LLM client here. Content generation lives in `.claude/skills/*/SKILL.md` files inside each wizard tool.

## What's in here

| Module | Purpose |
|---|---|
| `wizard_core.state_manager` | Generic workflow state machine. Per-stage status, file references, timestamps, optional git-commit hashes. Tool-name and stage-list parametrized via `WorkflowSpec`. |
| `wizard_core.git_manager` | Per-output-project git with safety guards that refuse to operate on the tool repo itself. Configured via `ToolGuard`. |
| `wizard_core.google_client` | Shared Google Drive / Slides / Docs access via the CultureBotAI service account. Optional extra: `pip install wizard-core[google]`. |
| `wizard_core.document_parsers` | PDF / DOCX / HTML / YAML parsers with lazy optional deps. Promoted from rrwrite in 0.2.0. |
| `wizard_core.citation_validator` | Defense-in-depth citation validation: entry, business-logic, assembly, and audit-trail layers. Paperpile + BibTeX support. Promoted from rrwrite in 0.2.0. |
| `wizard_core.literature_search` | Multi-source merge / dedup / sort with pluggable backends. Promoted from rrwrite in 0.2.0. |
| `wizard_core.schema_builder` | Build JSON submission / structure schemas from extracted requirements + caller-supplied templates. Promoted from rrwrite in 0.2.0. |
| `wizard_core.evidence_tracker` | Track claims and link them to citations / datasets / prior works; generates markdown + JSON reports. Promoted from pwiz in 0.2.0. |
| `wizard_core.manifest_generator` | Figure / table manifest generation and validation, with per-section lookup. Promoted from rrwrite in 0.2.0. |

No required runtime dependencies. Optional extras pull in libraries on demand:

| Extra | Pulls in | Used by |
|---|---|---|
| `wizard-core[parsers]` | PyPDF2, python-docx, python-pptx, bs4, lxml, pyyaml | `document_parsers` |
| `wizard-core[literature]` | requests, requests-cache | `literature_search` |
| `wizard-core[validation]` | jsonschema | `manifest_generator` validators |
| `wizard-core[google]` | google-auth, google-api-python-client | `google_client` |

## Install

```bash
pip install -e .
# with optional extras:
pip install -e ".[parsers,literature]"
```

## Use

```python
from wizard_core import StateManager, WorkflowSpec, ToolGuard

spec = WorkflowSpec(
    tool_name="swiz",
    state_dir_name=".swiz",
    stages=["source_analysis", "venue_assessment", "storyboard",
            "drafting", "asset_generation", "assembly", "critique"],
    guard=ToolGuard(
        tool_name="swiz",
        state_dir_name=".swiz",
        tool_repo_markers=("scripts/swiz_constants.py",),
        remote_url_patterns=("github.com/culturebotai/slide-wizard",),
    ),
)
manager = StateManager(output_dir="decks/demo_v1", spec=spec)
manager.update_stage("storyboard", status="completed", slide_count=12)
manager.commit_stage(stage="storyboard", files=["storyboard.json"], description="Initial storyboard")
```

## Status

0.2.0 — the six previously-placeholder modules (`document_parsers`, `citation_validator`, `literature_search`, `schema_builder`, `evidence_tracker`, `manifest_generator`) are now ported in and re-exported from `wizard_core`. Downstream wizards (proposal-wizard, repo-research-writer) are being refactored to import from here. See [wizard-claw](https://github.com/CultureBotAI/wizard-claw) for the orchestration layer that coordinates the migration.

## License

BSD 3-Clause. See `LICENSE`.
