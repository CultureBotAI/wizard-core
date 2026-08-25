# wizard-core — Claude operating guide

`wizard-core` is the shared library underneath the wizard tools. It has no runtime
dependencies; content generation happens inside Claude Code, not through an SDK.

Modules: `citation_validator`, `document_parsers`, `evidence_tracker`, `git_manager`,
`google_client`, `literature_search`, `manifest_generator`, `schema_builder`,
`state_manager`.

## Fact-based answers only — never guess, never fabricate

- Do not present an unverified claim as fact. Verify counts, versions,
  paths, diffs, test results, and behaviors with a tool call in the
  current session before reporting them, and cite the evidence
  (`file:line`, command output).
- Label inference as inference, and say what would confirm it.
- Say "I don't know" / "I couldn't verify" when verification fails —
  an honest gap beats a plausible guess.
- In reviews and reports, mark each finding **CONFIRMED** (reproduced)
  vs **PLAUSIBLE** (reasoned). Recalled or pattern-matched knowledge
  is not verification.

## This repo is the dependency root

Every change here can break the downstream wizards. Current consumers are
**slide-wizard** and **repo-research-writer**; proposal-wizard has removed its
wizard-core dependency. Before committing a change:

1. `python3 -m pytest tests/ -q` here.
2. Reinstall editable (`pip install -e /path/to/wizard-core`) into each consumer's
   environment.
3. Run each consumer's test suite against the new version.

## Output-project conventions

`git_manager.DEFAULT_GITIGNORE` excludes binaries wholesale and then whitelists the
well-known deliverable filenames each tool's assembler writes. Adding a new
deliverable artifact means adding its `!name.ext` line there — otherwise `git add`
on it fails and the artifact is silently never committed. Workspaces created before
a whitelist line existed are repaired by `GitManager.reconcile_gitignore()`, which
runs when `initialize_repository()` touches an already-initialized workspace.
