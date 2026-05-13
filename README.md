# wizard-core

Shared infrastructure for the CultureBotAI document-generation wizards: [slide-wizard](https://github.com/CultureBotAI/slide-wizard), [proposal-wizard](https://github.com/CultureBotAI/proposal-wizard) (private), and [repo-research-writer](https://github.com/CultureBotAI/repo-research-writer) (private).

## What's in here

| Module | Purpose |
|---|---|
| `wizard_core.state_manager` | Generic workflow state machine. Tracks per-stage status, file references, timestamps, git commits. Tool-name and stage-list parametrized. |
| `wizard_core.git_manager` | Per-output-project git repository management with safety guards (prevent commits to the tool repo from inside an output workspace). |
| `wizard_core.llm_client` | Thin Anthropic SDK wrapper. Prompt-caching breakpoints, message helpers, configurable default model. |
| `wizard_core.document_parsers` | (Phase 5) Manuscript/proposal/PDF/DOCX/PPTX readers. |
| `wizard_core.citation_validator` | (Phase 5) BibTeX cross-checking. |
| `wizard_core.literature_search` | (Phase 5) PubMed + Semantic Scholar queries. |
| `wizard_core.schema_builder` | (Phase 5) LinkML-driven config helpers. |

## Install

```bash
pip install -e .
# with optional extras:
pip install -e ".[literature,parsers]"
```

## Use

```python
from wizard_core.state_manager import StateManager, WorkflowSpec

spec = WorkflowSpec(
    tool_name="swiz",
    state_dir_name=".swiz",
    stages=["source_analysis", "venue_assessment", "storyboard",
            "drafting", "asset_generation", "assembly", "critique"],
)
manager = StateManager(output_dir="decks/demo_v1", spec=spec)
manager.update_stage("storyboard", status="completed", slide_count=12)
```

## Status

Phase 0 alpha. `state_manager`, `git_manager`, `llm_client` are functional; remaining modules are placeholders to be filled in as slide-wizard, proposal-wizard, and rrwrite migrate to them.

## License

BSD 3-Clause. See `LICENSE`.
