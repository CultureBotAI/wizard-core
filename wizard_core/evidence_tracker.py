"""Generic claim/evidence tracker for proposals, manuscripts, and decks.

Ported from `proposal-wizard/scripts/pwiz_evidence_tracker.py`. Tracks:

- **Claims** — assertions the document makes, tied to one or more evidence sources.
- **Citations** — publications (DOI, title, authors, year, venue, URL).
- **Datasets** — preliminary data / repositories backing methodological claims.
- **Prior proposals / works** — reused language and approaches from earlier outputs.

Generates a markdown evidence report and a JSON dump suitable for diffing
across revisions.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class EvidenceTracker:
    """Track document claims and link them to evidence sources."""

    def __init__(self, project_dir: str | Path, evidence_subdir: str = "evidence"):
        """
        Args:
            project_dir: Project / proposal / manuscript directory.
            evidence_subdir: Subdirectory under project_dir to hold the report
                and the JSON dump (default: ``evidence``).
        """
        self.project_dir = Path(project_dir).resolve()
        self.evidence_dir = self.project_dir / evidence_subdir
        self.logger = logging.getLogger(__name__)

        self.claims: List[Dict[str, Any]] = []
        self.citations: Dict[str, Dict[str, Any]] = {}
        self.datasets: Dict[str, Dict[str, Any]] = {}
        self.prior_proposals: Dict[str, Dict[str, Any]] = {}

        self.evidence_dir.mkdir(parents=True, exist_ok=True)

    # ----- claim tracking ----------------------------------------------------

    def add_claim(
        self,
        claim_text: str,
        section: str,
        evidence_sources: List[str],
        claim_type: str = "factual",
        context: Optional[str] = None,
    ) -> str:
        claim_id = f"claim_{len(self.claims) + 1:03d}"
        self.claims.append({
            "claim_id": claim_id,
            "text": claim_text,
            "section": section,
            "type": claim_type,
            "evidence_sources": evidence_sources,
            "context": context,
            "added_at": datetime.now().isoformat(),
        })
        self.logger.debug("Added claim %s: %s...", claim_id, claim_text[:50])
        return claim_id

    def link_citation(
        self,
        citation_key: str,
        doi: Optional[str] = None,
        title: Optional[str] = None,
        authors: Optional[str] = None,
        year: Optional[str] = None,
        venue: Optional[str] = None,
        url: Optional[str] = None,
        context: Optional[str] = None,
    ) -> str:
        self.citations[citation_key] = {
            "citation_key": citation_key,
            "doi": doi,
            "title": title,
            "authors": authors,
            "year": year,
            "venue": venue,
            "url": url,
            "context": context,
            "added_at": datetime.now().isoformat(),
        }
        return citation_key

    def link_dataset(
        self,
        dataset_id: str,
        name: str,
        description: Optional[str] = None,
        location: Optional[str] = None,
        size: Optional[str] = None,
        format: Optional[str] = None,
        context: Optional[str] = None,
    ) -> str:
        self.datasets[dataset_id] = {
            "dataset_id": dataset_id,
            "name": name,
            "description": description,
            "location": location,
            "size": size,
            "format": format,
            "context": context,
            "added_at": datetime.now().isoformat(),
        }
        return dataset_id

    def link_prior_proposal(
        self,
        source_id: str,
        title: str,
        funder: str,
        year: Optional[str] = None,
        funded: bool = False,
        sections_used: Optional[List[str]] = None,
        context: Optional[str] = None,
    ) -> str:
        self.prior_proposals[source_id] = {
            "source_id": source_id,
            "title": title,
            "funder": funder,
            "year": year,
            "funded": funded,
            "sections_used": sections_used or [],
            "context": context,
            "added_at": datetime.now().isoformat(),
        }
        return source_id

    # ----- validation --------------------------------------------------------

    def validate_evidence(self) -> Dict[str, Any]:
        """Quick sanity checks — DOIs present, dataset files exist, claims have sources."""
        validation = {
            "total_claims": len(self.claims),
            "total_citations": len(self.citations),
            "total_datasets": len(self.datasets),
            "total_prior_proposals": len(self.prior_proposals),
            "validated_citations": 0,
            "validated_datasets": 0,
            "validated_proposals": 0,
            "issues": [],
        }
        for key, citation in self.citations.items():
            if citation.get("doi"):
                validation["validated_citations"] += 1
            else:
                validation["issues"].append(f"Citation {key} missing DOI")
        for ds_id, ds in self.datasets.items():
            loc = ds.get("location")
            if loc and Path(loc).exists():
                validation["validated_datasets"] += 1
            elif loc:
                validation["issues"].append(f"Dataset {ds_id} file not found: {loc}")
        validation["validated_proposals"] = len(self.prior_proposals)
        for claim in self.claims:
            if not claim.get("evidence_sources"):
                validation["issues"].append(f"Claim {claim['claim_id']} has no evidence sources")
        return validation

    # ----- reporting ---------------------------------------------------------

    def generate_report(self, output_file: Optional[str] = None) -> str:
        path = self.project_dir / (output_file or "evidence/evidence_report.md")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self._format_evidence_report())
        self.logger.info("✓ Evidence report generated: %s", path)
        return str(path)

    def _format_evidence_report(self) -> str:
        lines = [
            "# Evidence Report",
            "",
            f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "**Purpose**: Track all claims and their supporting evidence",
            "",
            "---",
            "",
            "## Summary",
            "",
            f"- **Total Claims**: {len(self.claims)}",
            f"- **Citations**: {len(self.citations)}",
            f"- **Datasets**: {len(self.datasets)}",
            f"- **Prior Proposals**: {len(self.prior_proposals)}",
            "",
            "---",
            "",
            "## Claims by Section",
            "",
        ]

        by_section: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for claim in self.claims:
            by_section[claim["section"]].append(claim)

        for section in sorted(by_section):
            section_claims = by_section[section]
            lines += [f"### {section.replace('_', ' ').title()}", "", f"**Claims**: {len(section_claims)}", ""]
            for claim in section_claims:
                lines += [
                    f"#### {claim['claim_id']}",
                    "",
                    f"**Claim**: {claim['text']}",
                    "",
                    f"**Type**: {claim['type']}",
                    "",
                    "**Evidence Sources**:",
                    "",
                ]
                lines += [f"- {s}" for s in claim.get("evidence_sources", [])]
                if claim.get("context"):
                    lines += ["", f"**Context**: {claim['context']}"]
                lines += ["", "---", ""]

        if self.citations:
            lines += ["", "## Citations", ""]
            for key in sorted(self.citations):
                cit = self.citations[key]
                lines += [f"### {key}", ""]
                if cit.get("title"):
                    lines.append(f"**Title**: {cit['title']}")
                if cit.get("authors"):
                    lines.append(f"**Authors**: {cit['authors']}")
                if cit.get("venue"):
                    lines.append(f"**Venue**: {cit['venue']}, {cit.get('year', 'n.d.')}")
                if cit.get("doi"):
                    lines.append(f"**DOI**: {cit['doi']}")
                if cit.get("url"):
                    lines.append(f"**URL**: {cit['url']}")
                if cit.get("context"):
                    lines += ["", f"**Context**: {cit['context']}"]
                lines += ["", "---", ""]

        if self.datasets:
            lines += ["", "## Datasets", ""]
            for ds_id in sorted(self.datasets):
                ds = self.datasets[ds_id]
                lines += [f"### {ds_id}", "", f"**Name**: {ds['name']}"]
                if ds.get("description"):
                    lines.append(f"**Description**: {ds['description']}")
                if ds.get("location"):
                    lines.append(f"**Location**: `{ds['location']}`")
                if ds.get("size"):
                    lines.append(f"**Size**: {ds['size']}")
                if ds.get("format"):
                    lines.append(f"**Format**: {ds['format']}")
                if ds.get("context"):
                    lines += ["", f"**Context**: {ds['context']}"]
                lines += ["", "---", ""]

        if self.prior_proposals:
            lines += ["", "## Prior Proposals", ""]
            for src_id in sorted(self.prior_proposals):
                pp = self.prior_proposals[src_id]
                lines += [f"### {src_id}", "", f"**Title**: {pp['title']}", f"**Funder**: {pp['funder']}"]
                if pp.get("year"):
                    lines.append(f"**Year**: {pp['year']}")
                lines.append(f"**Status**: {'✅ Funded' if pp.get('funded') else '❌ Not Funded'}")
                if pp.get("sections_used"):
                    lines += ["", "**Sections Used**:", ""]
                    lines += [f"- {s}" for s in pp["sections_used"]]
                if pp.get("context"):
                    lines += ["", f"**Context**: {pp['context']}"]
                lines += ["", "---", ""]

        return "\n".join(lines)

    def save_evidence_data(self, output_file: Optional[str] = None) -> str:
        path = self.project_dir / (output_file or "evidence/evidence_data.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated_at": datetime.now().isoformat(),
            "claims": self.claims,
            "citations": self.citations,
            "datasets": self.datasets,
            "prior_proposals": self.prior_proposals,
        }
        path.write_text(json.dumps(payload, indent=2))
        return str(path)

    def load_evidence_data(self, input_file: str) -> None:
        path = self.project_dir / input_file
        if not path.exists():
            raise FileNotFoundError(f"Evidence data not found: {path}")
        data = json.loads(path.read_text())
        self.claims = data.get("claims", [])
        self.citations = data.get("citations", {})
        self.datasets = data.get("datasets", {})
        self.prior_proposals = data.get("prior_proposals", {})

    # ----- queries -----------------------------------------------------------

    def get_claims_by_section(self, section: str) -> List[Dict[str, Any]]:
        return [c for c in self.claims if c["section"] == section]

    def get_claims_by_type(self, claim_type: str) -> List[Dict[str, Any]]:
        return [c for c in self.claims if c["type"] == claim_type]

    def get_citation(self, key: str) -> Optional[Dict[str, Any]]:
        return self.citations.get(key)

    def get_dataset(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        return self.datasets.get(dataset_id)

    def get_prior_proposal(self, source_id: str) -> Optional[Dict[str, Any]]:
        return self.prior_proposals.get(source_id)


# Functional alias kept for the placeholder API.
def track_evidence(project_dir: str | Path) -> EvidenceTracker:
    return EvidenceTracker(project_dir)
