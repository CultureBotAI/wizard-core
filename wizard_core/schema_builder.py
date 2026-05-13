"""Build journal-submission JSON schemas from extracted requirements.

Ported from `repo-research-writer/scripts/rrwrite_schema_builder.py`.
Templates (base submission requirements, base manuscript structure) are
loaded from a caller-provided directory rather than baked into the
library — different tools (rrwrite, future slide-wizard venue specs,
proposal-wizard funder templates) can supply their own.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class SchemaBuilderError(Exception):
    """Raised when schema building fails."""


class SchemaBuilder:
    """Build submission / structure schemas from extracted requirements.

    Args:
        templates_dir: Directory containing template JSON files. Each tool
            should provide its own templates (e.g. rrwrite's
            ``schemas/templates/base_submission_requirements.json``).
    """

    def __init__(self, templates_dir: Path):
        self.templates_dir = Path(templates_dir)
        if not self.templates_dir.exists():
            raise SchemaBuilderError(f"Templates directory not found: {templates_dir}")
        self.base_submission = self._load_template("base_submission_requirements.json")
        self.base_structure = self._load_template("base_manuscript_structure.json")

    def _load_template(self, filename: str) -> Dict[str, Any]:
        path = self.templates_dir / filename
        if not path.exists():
            raise SchemaBuilderError(f"Template not found: {path}")
        try:
            with open(path) as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise SchemaBuilderError(f"Invalid JSON in template {filename}: {e}") from e

    def build_submission_schema(
        self,
        journal_name: str,
        requirements: Dict[str, Any],
        source_type: str,
        source_path: str,
    ) -> Dict[str, Any]:
        schema = self.base_submission.copy()
        schema["journal"] = {
            "name": journal_name,
            "short_name": self._generate_short_name(journal_name),
            "publisher": requirements.get("publisher", "Unknown"),
            "url": requirements.get("journal_url", ""),
            "submission_url": source_path if source_type == "url" else "",
        }
        schema["requirements"] = {
            "word_limits": dict(requirements.get("word_limits", {})),
            "section_requirements": {
                "required_sections": requirements.get("section_requirements", {}).get("required_sections", []),
                "optional_sections": requirements.get("section_requirements", {}).get("optional_sections", []),
                "section_order": requirements.get("section_requirements", {}).get("section_order", []),
                "special_requirements": {},
            },
            "citation_requirements": {
                "style": requirements.get("citation_style", {}).get("style", "Unknown"),
                "max_references": requirements.get("citation_style", {}).get("max_references"),
                "min_references": requirements.get("citation_style", {}).get("min_references"),
                "reference_formatting": requirements.get("citation_style", {}).get("formatting", ""),
            },
            "figure_table_requirements": {
                "max_figures": requirements.get("figure_table_limits", {}).get("max_figures"),
                "max_tables": requirements.get("figure_table_limits", {}).get("max_tables"),
                "figure_formats": ["PNG", "PDF", "TIFF", "EPS"],
                "resolution_requirements": "300 DPI minimum",
            },
            "formatting_requirements": requirements.get("formatting_rules", {}),
            "special_requirements": requirements.get("special_requirements", []),
        }
        schema["metadata"] = {
            "schema_version": "1.0",
            "generated_at": datetime.now().isoformat(),
            "source_type": source_type,
            "source_path": source_path,
            "validated": False,
            "notes": f"Auto-generated from {source_type} source",
        }
        return schema

    def build_manuscript_schema(
        self,
        journal_name: str,
        requirements: Dict[str, Any],
        source_type: str,
    ) -> Dict[str, Any]:
        schema = self.base_structure.copy()
        schema["journal"] = {"name": journal_name}

        section_req = requirements.get("section_requirements", {})
        required_sections = section_req.get("required_sections", [])
        section_order = section_req.get("section_order", required_sections)
        word_limits = requirements.get("word_limits", {})

        sections = []
        for name in section_order:
            sec = {
                "name": name,
                "required": name in required_sections,
                "heading_level": 1 if name == "abstract" else 2,
                "description": self._section_description(name),
            }
            if name in word_limits:
                sec["word_limit"] = word_limits[name]
            sections.append(sec)

        schema["structure"] = {
            "sections": sections,
            "global_constraints": self._global_constraints(requirements),
            "ordering_rules": {"strict_order": True, "allowed_deviations": []},
        }
        schema["metadata"] = {
            "schema_version": "1.0",
            "generated_at": datetime.now().isoformat(),
            "source_type": source_type,
            "validated": False,
        }
        return schema

    @staticmethod
    def _global_constraints(requirements: Dict[str, Any]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        wl = requirements.get("word_limits", {})
        if "total_manuscript" in wl:
            out["total_word_count"] = wl["total_manuscript"]
        ft = requirements.get("figure_table_limits", {})
        if "max_figures" in ft:
            out["max_figures"] = ft["max_figures"]
        if "max_tables" in ft:
            out["max_tables"] = ft["max_tables"]
        cit = requirements.get("citation_style", {})
        if "max_references" in cit:
            out["max_references"] = cit["max_references"]
        return out

    @staticmethod
    def _section_description(name: str) -> str:
        descriptions = {
            "abstract": "Concise summary of the research question, methods, results, and conclusions",
            "introduction": "Background, motivation, and research objectives",
            "methods": "Detailed description of experimental procedures and computational methods",
            "results": "Presentation of findings with figures and tables",
            "discussion": "Interpretation of results, implications, and limitations",
            "availability": "Data and code availability statements",
            "author_summary": "Lay summary of the significance and impact",
            "acknowledgments": "Funding sources and acknowledgments",
            "references": "Bibliography of cited works",
        }
        return descriptions.get(name, "")

    @staticmethod
    def _generate_short_name(full_name: str) -> str:
        words = full_name.split()
        filtered = [w for w in words if w.lower() not in ("the", "journal", "of", "and")]
        return " ".join(filtered[:2]) if len(filtered) > 2 else full_name

    @staticmethod
    def validate_schema(schema: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        if "journal" not in schema:
            errors.append("Missing required key: journal")
        elif "name" not in schema["journal"]:
            errors.append("Missing journal name")
        if "metadata" not in schema:
            errors.append("Missing required key: metadata")
        else:
            meta = schema["metadata"]
            if "generated_at" not in meta:
                errors.append("Missing metadata.generated_at")
            if "source_type" not in meta:
                errors.append("Missing metadata.source_type")
        if "requirements" not in schema and "structure" not in schema:
            errors.append("Missing either 'requirements' or 'structure' key")
        return len(errors) == 0, errors


def build_from_linkml(*args: Any, **kwargs: Any) -> Any:  # pragma: no cover
    """Placeholder for the LinkML branch that hasn't been implemented yet."""
    raise NotImplementedError(
        "LinkML schema-building is not implemented yet; use SchemaBuilder for JSON-schema flows."
    )
