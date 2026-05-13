"""Figure/table manifest generation and validation.

Ported from `repo-research-writer/scripts/rrwrite_manifest_generator.py`.
Generates JSON manifests for figures and tables extracted from
repositories or generated during analysis, with priority-based sorting
and per-section lookup. Optional jsonschema-based validation.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


class ManifestGenerator:
    """Generate JSON manifests for figures and tables under a project dir."""

    def __init__(self, project_dir: Path):
        """
        Args:
            project_dir: Project / manuscript directory. ``figures/`` and
                ``tables/`` subdirectories will be created on demand.
        """
        self.project_dir = Path(project_dir)
        self.figures_dir = self.project_dir / "figures"
        self.tables_dir = self.project_dir / "tables"

    def create_figure_manifest(self, figures: List[Dict[str, Any]]) -> Path:
        manifest_path = self.figures_dir / "figure_manifest.json"
        self.figures_dir.mkdir(parents=True, exist_ok=True)
        sorted_figures = sorted(figures, key=lambda f: (f["priority"], f["id"]))
        manifest = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "total_figures": len(figures),
            "figures_from_repo": sum(1 for f in figures if f["source"] == "from_repo"),
            "figures_generated": sum(1 for f in figures if f["source"] == "generated"),
            "figures": sorted_figures,
        }
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        return manifest_path

    def create_table_manifest(self, tables: List[Dict[str, Any]]) -> Path:
        manifest_path = self.tables_dir / "table_manifest.json"
        self.tables_dir.mkdir(parents=True, exist_ok=True)
        sorted_tables = sorted(tables, key=lambda t: (t["priority"], t["id"]))
        manifest = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "total_tables": len(tables),
            "tables_from_repo": sum(1 for t in tables if t["source"] == "from_repo"),
            "tables_generated": sum(1 for t in tables if t["source"] == "generated"),
            "tables": sorted_tables,
        }
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        return manifest_path

    def load_figure_manifest(self) -> Dict[str, Any]:
        path = self.figures_dir / "figure_manifest.json"
        if not path.exists():
            return {}
        with open(path) as f:
            return json.load(f)

    def load_table_manifest(self) -> Dict[str, Any]:
        path = self.tables_dir / "table_manifest.json"
        if not path.exists():
            return {}
        with open(path) as f:
            return json.load(f)

    def get_figures_for_section(self, section_name: str, prioritize_repo: bool = True) -> List[Dict[str, Any]]:
        manifest = self.load_figure_manifest()
        if not manifest:
            return []
        out = [fig for fig in manifest.get("figures", []) if section_name in fig.get("recommended_sections", [])]
        if prioritize_repo:
            out.sort(key=lambda f: f["priority"])
        return out

    def get_tables_for_section(self, section_name: str, prioritize_repo: bool = True) -> List[Dict[str, Any]]:
        manifest = self.load_table_manifest()
        if not manifest:
            return []
        out = [t for t in manifest.get("tables", []) if section_name in t.get("recommended_sections", [])]
        if prioritize_repo:
            out.sort(key=lambda t: t["priority"])
        return out


class ManifestValidator:
    """Validate figure/table manifests against JSON schemas."""

    def __init__(self, schemas_dir: Path):
        self.schemas_dir = Path(schemas_dir)

    def validate_figure_manifest(self, manifest_path: Path) -> Tuple[bool, List[str]]:
        return self._validate(manifest_path, "figure_manifest_schema.json")

    def validate_table_manifest(self, manifest_path: Path) -> Tuple[bool, List[str]]:
        return self._validate(manifest_path, "table_manifest_schema.json")

    def _validate(self, manifest_path: Path, schema_name: str) -> Tuple[bool, List[str]]:
        if not HAS_JSONSCHEMA:
            return False, ["jsonschema not installed. Install with: pip install jsonschema"]
        schema_path = self.schemas_dir / schema_name
        if not schema_path.exists():
            return False, [f"Schema not found: {schema_path}"]
        with open(schema_path) as f:
            schema = json.load(f)
        with open(manifest_path) as f:
            manifest = json.load(f)
        try:
            jsonschema.validate(instance=manifest, schema=schema)
            return True, []
        except jsonschema.exceptions.ValidationError as e:
            return False, [str(e)]


# Functional alias kept for symmetry with the placeholder API.
def generate_manifest(project_dir: Path, figures: List[Dict[str, Any]] | None = None, tables: List[Dict[str, Any]] | None = None) -> Dict[str, Path]:
    """Convenience wrapper: write whichever manifests are provided.

    Returns a dict of `{kind: manifest_path}` for the kinds that were created.
    """
    gen = ManifestGenerator(project_dir)
    out: Dict[str, Path] = {}
    if figures is not None:
        out["figures"] = gen.create_figure_manifest(figures)
    if tables is not None:
        out["tables"] = gen.create_table_manifest(tables)
    return out
