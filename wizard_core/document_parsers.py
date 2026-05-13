"""Document parsers for manuscript/proposal/PDF/DOCX/PPTX inputs.

Placeholder module. Phase 5 will port the real parsers from
`repo-research-writer/scripts/rrwrite_document_parsers.py` (403 lines) and
extend with python-pptx-based slide-deck readers needed by slide-wizard.

Until then, importing this module is harmless; functions raise
NotImplementedError when called.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict


def parse_markdown(path: Path) -> Dict[str, Any]:
    raise NotImplementedError("Port from rrwrite_document_parsers in Phase 5")


def parse_docx(path: Path) -> Dict[str, Any]:
    raise NotImplementedError("Port from rrwrite_document_parsers in Phase 5")


def parse_pdf(path: Path) -> Dict[str, Any]:
    raise NotImplementedError("Port from rrwrite_document_parsers in Phase 5")


def parse_pptx(path: Path) -> Dict[str, Any]:
    """Extract slides, text frames, speaker notes, image refs from a .pptx file.

    To be implemented in slide-wizard Phase 3 using python-pptx, then lifted
    here for sharing.
    """
    raise NotImplementedError("Implemented in slide-wizard Phase 3")
