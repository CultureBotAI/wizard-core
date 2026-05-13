"""Defense-in-depth citation validation framework.

Ported from `repo-research-writer/scripts/rrwrite_citation_validator.py`.

Four layers:
    Layer 1 — Entry validation (fail fast at draft time)
    Layer 2 — Business logic validation (section appropriateness)
    Layer 3 — Assembly validation (completeness at compilation)
    Layer 4 — Audit trail (forensics)

Each layer is independently usable; `validate_all_layers` runs them in order.
"""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


class CitationError(Exception):
    """Base citation error."""


class CitationNotFoundError(CitationError):
    """Citation key not found in evidence file."""


class CitationMismatchError(CitationError):
    """Mismatch between text citations and bibliography."""


class CitationAppropriatenessWarning(Warning):
    """Possibly inappropriate citation for a section type."""


# ----- Layer 1: Entry Validation --------------------------------------------

class CitationEntryValidator:
    """Fast-fail validation at entry time."""

    @staticmethod
    def load_evidence_keys(evidence_csv: Path) -> Set[str]:
        if not evidence_csv.exists():
            return set()
        keys: Set[str] = set()
        try:
            with open(evidence_csv, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if "citation_key" in row:
                        keys.add(row["citation_key"])
        except Exception as e:  # noqa: BLE001 — preserve original lenient behaviour
            print(f"Warning: Could not load evidence file: {e}")
        return keys

    @staticmethod
    def validate_at_entry(citation_key: str, evidence_csv: Path) -> None:
        keys = CitationEntryValidator.load_evidence_keys(evidence_csv)
        if citation_key not in keys:
            raise CitationNotFoundError(
                "\n❌ Citation Verification Failed\n\n"
                f"Citation [{citation_key}] not in {evidence_csv.name}\n\n"
                "Why this matters: claims without evidence mean:\n"
                "1. Reviewers will request verification\n"
                "2. Retraction risk if source disputed\n"
                "3. Ethical violation if claim unsupported\n\n"
                "Next steps:\n"
                "1. Search literature for a supporting source\n"
                "2. Add the citation key + DOI + quote to the evidence file\n"
                "3. Re-run validation\n"
            )

    @staticmethod
    def validate_multiple(citation_keys: List[str], evidence_csv: Path) -> Tuple[List[str], List[str]]:
        keys = CitationEntryValidator.load_evidence_keys(evidence_csv)
        valid = [k for k in citation_keys if k in keys]
        invalid = [k for k in citation_keys if k not in keys]
        return valid, invalid


# ----- Layer 2: Business Logic Validation -----------------------------------

class CitationBusinessValidator:
    """Validate citations against per-section rules."""

    SECTION_RULES: Dict[str, Dict[str, object]] = {
        "abstract": {
            "max_citations": 2,
            "reason": "Abstracts should be self-contained; citations rarely appropriate",
            "allowed_types": ["seminal"],
        },
        "introduction": {
            "max_citations": None,
            "reason": "Broad background; most citation types appropriate",
            "allowed_types": ["seminal", "review", "recent", "tool"],
        },
        "methods": {
            "max_citations": None,
            "reason": "Should cite tools/datasets/protocols actually used",
            "allowed_types": ["tool", "protocol", "dataset"],
            "forbidden_types": ["review"],
        },
        "results": {
            "max_citations": None,
            "reason": "Should compare to other studies, cite benchmarks",
            "allowed_types": ["recent", "benchmark"],
            "forbidden_types": ["review"],
        },
        "discussion": {
            "max_citations": None,
            "reason": "Broad interpretation; most citation types appropriate",
            "allowed_types": ["seminal", "review", "recent", "tool"],
        },
    }

    def __init__(self, evidence_csv: Path):
        self.evidence_csv = evidence_csv
        self.warnings: List[str] = []

    def _load_citation_metadata(self) -> Dict[str, Dict[str, str]]:
        meta: Dict[str, Dict[str, str]] = {}
        if not self.evidence_csv.exists():
            return meta
        try:
            with open(self.evidence_csv, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if "citation_key" in row:
                        meta[row["citation_key"]] = {
                            "title": row.get("title", ""),
                            "abstract": row.get("abstract", ""),
                            "doi": row.get("doi", ""),
                            "year": row.get("year", ""),
                            "citation_type": row.get("citation_type", "unknown"),
                        }
        except Exception as e:  # noqa: BLE001
            print(f"Warning: Could not load citation metadata: {e}")
        return meta

    def _infer_citation_type(self, metadata: Dict[str, str]) -> str:
        title = metadata.get("title", "").lower()
        if any(w in title for w in ("software", "tool", "pipeline", "package", "algorithm")):
            return "tool"
        if any(w in title for w in ("review", "survey", "overview", "perspectives")):
            return "review"
        if any(w in title for w in ("protocol", "method", "procedure", "workflow")):
            return "protocol"
        if any(w in title for w in ("database", "dataset", "repository", "collection")):
            return "dataset"
        if any(w in title for w in ("benchmark", "comparison", "evaluation")):
            return "benchmark"
        year = metadata.get("year", "")
        if year:
            try:
                y = int(year)
                if y >= datetime.now().year - 5:
                    return "recent"
                if y < datetime.now().year - 10:
                    return "seminal"
            except ValueError:
                pass
        return "unknown"

    def validate_section_appropriateness(self, section: str, citations: List[str]) -> List[str]:
        self.warnings = []
        rules = self.SECTION_RULES.get(section.lower())
        if not rules:
            return self.warnings
        metadata = self._load_citation_metadata()
        max_cit = rules.get("max_citations")
        if max_cit and len(citations) > max_cit:  # type: ignore[operator]
            self.warnings.append(
                f"⚠️  {section} has {len(citations)} citations, but should have ≤{max_cit}. {rules['reason']}"
            )
        for cit in citations:
            md = metadata.get(cit)
            if not md:
                continue
            cit_type = md.get("citation_type") or "unknown"
            if cit_type == "unknown":
                cit_type = self._infer_citation_type(md)
            forbidden = rules.get("forbidden_types", []) or []
            allowed = rules.get("allowed_types", []) or []
            if cit_type in forbidden:
                self.warnings.append(
                    f"⚠️  Citation [{cit}] appears to be {cit_type}, not appropriate for {section}. {rules['reason']}"
                )
            elif allowed and cit_type not in allowed:
                self.warnings.append(
                    f"⚠️  Citation [{cit}] appears to be {cit_type}; {section} typically uses: {', '.join(allowed)}"
                )
        return self.warnings


# ----- Paperpile support ----------------------------------------------------

class PaperpileCitationHandler:
    """Resolve Paperpile inline codes to BibTeX keys via a mapping file."""

    PAPERPILE_RE = re.compile(r"\[.*?\]\(https://paperpile\.com/c/[^/]+/([^\)]+)\)")

    @staticmethod
    def extract_paperpile_citations(text: str) -> List[str]:
        return PaperpileCitationHandler.PAPERPILE_RE.findall(text)

    @staticmethod
    def load_paperpile_mapping(mapping_file: Path) -> Dict[str, str]:
        if not mapping_file.exists():
            return {}
        try:
            with open(mapping_file, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:  # noqa: BLE001
            print(f"Warning: Could not load Paperpile mapping: {e}")
            return {}

    @staticmethod
    def map_to_bibtex_keys(codes: List[str], mapping: Dict[str, str]) -> Tuple[List[str], List[str]]:
        mapped: List[str] = []
        unmapped: List[str] = []
        for code in codes:
            (mapped if code in mapping else unmapped).append(mapping.get(code, code))
        return mapped, unmapped

    @staticmethod
    def extract_and_map_citations(manuscript_path: Path, mapping_file: Path) -> Tuple[Set[str], List[str]]:
        if not manuscript_path.exists():
            return set(), []
        text = manuscript_path.read_text(encoding="utf-8")
        codes = PaperpileCitationHandler.extract_paperpile_citations(text)
        mapping = PaperpileCitationHandler.load_paperpile_mapping(mapping_file)
        mapped, unmapped = PaperpileCitationHandler.map_to_bibtex_keys(codes, mapping)
        return set(mapped), unmapped


# ----- Layer 3: Assembly Validation -----------------------------------------

class CitationAssemblyValidator:
    """Validate completeness at manuscript compilation."""

    BIBTEX_RE = re.compile(r"\[([a-zA-Z]+\d{4}[a-z]?)\]")
    BIB_KEY_RE = re.compile(r"@\w+\{([^,]+),")

    @staticmethod
    def extract_citations_from_text(
        manuscript_path: Path,
        format: str = "bibtex",
        paperpile_mapping: Optional[Path] = None,
    ) -> Set[str]:
        if not manuscript_path.exists():
            return set()
        if format == "paperpile":
            if not paperpile_mapping:
                raise ValueError("paperpile_mapping required when format='paperpile'")
            mapped, unmapped = PaperpileCitationHandler.extract_and_map_citations(manuscript_path, paperpile_mapping)
            if unmapped:
                print(f"Warning: {len(unmapped)} Paperpile codes not in mapping: {unmapped[:5]}")
            return mapped
        content = manuscript_path.read_text(encoding="utf-8")
        return set(CitationAssemblyValidator.BIBTEX_RE.findall(content))

    @staticmethod
    def extract_citations_from_bib(bib_path: Path) -> Set[str]:
        if not bib_path.exists():
            return set()
        return set(CitationAssemblyValidator.BIB_KEY_RE.findall(bib_path.read_text(encoding="utf-8")))

    @staticmethod
    def validate_citation_completeness(
        manuscript_path: Path,
        bib_path: Path,
        format: str = "bibtex",
        paperpile_mapping: Optional[Path] = None,
    ) -> Tuple[Set[str], Set[str]]:
        text_cites = CitationAssemblyValidator.extract_citations_from_text(manuscript_path, format=format, paperpile_mapping=paperpile_mapping)
        bib_cites = CitationAssemblyValidator.extract_citations_from_bib(bib_path)
        orphaned_text = text_cites - bib_cites
        orphaned_bib = bib_cites - text_cites
        if orphaned_text or orphaned_bib:
            msg = ["\n❌ Citation Mismatch Error\n"]
            if orphaned_text:
                msg.append(f"Citations in text but not in bibliography ({len(orphaned_text)}):")
                msg.extend(f"  - [{c}]" for c in sorted(orphaned_text))
            if orphaned_bib:
                msg.append(f"Citations in bibliography but not in text ({len(orphaned_bib)}):")
                msg.extend(f"  - [{c}]" for c in sorted(orphaned_bib))
            raise CitationMismatchError("\n".join(msg))
        return orphaned_text, orphaned_bib


# ----- Layer 4: Audit Trail -------------------------------------------------

class CitationAuditor:
    """Append-only JSONL audit log of citation usages."""

    def __init__(self, audit_log_path: Path):
        self.audit_log_path = audit_log_path
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_citation_usage(self, section: str, citation: str, context: str, evidence_csv: Path) -> None:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "section": section,
            "citation": citation,
            "context": context[:200],
            "doi_verified": self._verify_doi(citation, evidence_csv),
        }
        with open(self.audit_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    @staticmethod
    def _verify_doi(citation_key: str, evidence_csv: Path) -> bool:
        if not evidence_csv.exists():
            return False
        try:
            with open(evidence_csv, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if row.get("citation_key") == citation_key:
                        doi = row.get("doi", "")
                        return bool(doi and doi.startswith("10."))
        except Exception:  # noqa: BLE001 — audit log is best-effort
            pass
        return False

    def get_citation_history(self, citation: str) -> List[Dict[str, object]]:
        if not self.audit_log_path.exists():
            return []
        out: List[Dict[str, object]] = []
        with open(self.audit_log_path, encoding="utf-8") as f:
            for line in f:
                entry = json.loads(line)
                if entry.get("citation") == citation:
                    out.append(entry)
        return out

    def export_audit_report(self, output_path: Path) -> None:
        if not self.audit_log_path.exists():
            print("No audit log found")
            return
        entries: List[Dict[str, object]] = []
        with open(self.audit_log_path, encoding="utf-8") as f:
            for line in f:
                entries.append(json.loads(line))
        by_cit: Dict[str, List[Dict[str, object]]] = {}
        for entry in entries:
            by_cit.setdefault(entry["citation"], []).append(entry)  # type: ignore[index]
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("# Citation Audit Report\n\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n\n")
            f.write(f"Total citation usages: {len(entries)}\n\n## Citations by Key\n\n")
            for cit in sorted(by_cit):
                usages = by_cit[cit]
                f.write(f"### [{cit}]\n\n")
                f.write(f"- Used {len(usages)} time(s)\n")
                f.write(f"- DOI verified: {usages[0]['doi_verified']}\n")
                f.write(f"- Sections: {', '.join(sorted(set(u['section'] for u in usages)))}\n\n")  # type: ignore[arg-type]


# ----- Convenience ----------------------------------------------------------

def validate_all_layers(
    citation_keys: List[str],
    section: str,
    evidence_csv: Path,
    manuscript_path: Optional[Path] = None,
    bib_path: Optional[Path] = None,
    audit_log_path: Optional[Path] = None,
    format: str = "bibtex",
    paperpile_mapping: Optional[Path] = None,
) -> Tuple[bool, List[str]]:
    """Run layers 1–4 (audit is opt-in by passing ``audit_log_path``)."""
    errors: List[str] = []

    try:
        for cit in citation_keys:
            CitationEntryValidator.validate_at_entry(cit, evidence_csv)
    except CitationNotFoundError as e:
        errors.append(str(e))
        return False, errors

    biz = CitationBusinessValidator(evidence_csv)
    errors.extend(biz.validate_section_appropriateness(section, citation_keys))

    if manuscript_path and bib_path:
        try:
            CitationAssemblyValidator.validate_citation_completeness(
                manuscript_path, bib_path, format=format, paperpile_mapping=paperpile_mapping
            )
        except CitationMismatchError as e:
            errors.append(str(e))
            return False, errors

    if audit_log_path:
        auditor = CitationAuditor(audit_log_path)
        for cit in citation_keys:
            auditor.log_citation_usage(section, cit, "", evidence_csv)

    return len(errors) == 0, errors


# Backwards-compatible name kept for the placeholder API.
def validate_citations(*args: object, **kwargs: object) -> Tuple[bool, List[str]]:
    return validate_all_layers(*args, **kwargs)  # type: ignore[arg-type]
