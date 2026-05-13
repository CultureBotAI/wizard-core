# wizard-core

Shared infrastructure for the CultureBotAI document-generation wizards: [slide-wizard](https://github.com/CultureBotAI/slide-wizard), [proposal-wizard](https://github.com/CultureBotAI/proposal-wizard), and [repo-research-writer](https://github.com/CultureBotAI/repo-research-writer).

These wizards run as **Claude Code skills** — Claude itself is the LLM runtime. wizard-core provides only the deterministic infrastructure the wizards all need: workflow state, per-output-project git management, and (Phase 5) shared document parsers and validators. There is no LLM client here. Content generation lives in `.claude/skills/*/SKILL.md` files inside each wizard tool.

## What's in here

| Module | Purpose |
|---|---|
| `wizard_core.state_manager` | Generic workflow state machine. Per-stage status, file references, timestamps, optional git-commit hashes. Tool-name and stage-list parametrized via `WorkflowSpec`. |
| `wizard_core.git_manager` | Per-output-project git with safety guards that refuse to operate on the tool repo itself. Configured via `ToolGuard`. |
| `wizard_core.document_parsers` | (Phase 5) Manuscript/proposal/PDF/DOCX/PPTX readers. |
| `wizard_core.citation_validator` | (Phase 5) BibTeX cross-checking. |
| `wizard_core.literature_search` | (Phase 5) PubMed + Semantic Scholar queries. |
| `wizard_core.schema_builder` | (Phase 5) LinkML-driven config helpers. |
| `wizard_core.evidence_tracker` | (Phase 5) Claim-to-evidence linkage. |
| `wizard_core.manifest_generator` | (Phase 5) Output bundle manifests. |

No runtime dependencies. Optional extras (`[parsers]`, `[literature]`) pull in libraries for Phase 5 modules as they're ported.

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

Phase 0 alpha. `state_manager` and `git_manager` are functional and tested (6 passing). Phase 5 modules are placeholders to be filled in as slide-wizard, proposal-wizard, and rrwrite migrate.

## License

BSD 3-Clause. See `LICENSE`.
