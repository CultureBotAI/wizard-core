"""Literature search across PubMed, Semantic Scholar, OpenAlex, Europe PMC.

Ported from `repo-research-writer/scripts/rrwrite-search-literature.py`.

The original delegates each backend to a sibling `rrwrite-api-*.py` script
via subprocess. That coupling is moved here as an *injectable* `backends`
table — by default each backend is `None` (raising NotImplementedError on
use), but a caller can pass a `{source_name: callable}` mapping that
returns a list of paper dicts. This lets each downstream tool plug in its
own HTTP client without wizard-core itself depending on requests / etc.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

try:
    import requests_cache  # noqa: F401
    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False


BackendFn = Callable[[str, int], List[Dict[str, Any]]]


def setup_cache(cache_dir: Path, expire_after: int = 86400) -> None:
    """Install a 24-hour SQLite cache via requests-cache, if available."""
    if not CACHE_AVAILABLE:
        return
    import requests_cache as rc  # local import keeps top-level cheap
    cache_dir.mkdir(parents=True, exist_ok=True)
    rc.install_cache(str(cache_dir / "literature_cache"), backend="sqlite", expire_after=expire_after)


def deduplicate_papers(papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicates by DOI then by exact title (lowercased)."""
    seen_dois: set[str] = set()
    seen_titles: set[str] = set()
    out: List[Dict[str, Any]] = []
    for p in papers:
        doi = (p.get("doi") or "").strip().lower()
        title = (p.get("title") or "").strip().lower()
        if doi and doi in seen_dois:
            continue
        if title and title in seen_titles:
            continue
        out.append(p)
        if doi:
            seen_dois.add(doi)
        if title:
            seen_titles.add(title)
    return out


def _sort_key(paper: Dict[str, Any]) -> tuple[int, int]:
    citations = paper.get("citations") or paper.get("citationCount") or 0
    year = paper.get("year", 0)
    if isinstance(year, str):
        try:
            year = int(year)
        except ValueError:
            year = 0
    return (-int(citations), -int(year))


def search_literature(
    query: str,
    max_results: int = 20,
    backends: Optional[Dict[str, BackendFn]] = None,
    cache_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Search every backend, merge, dedup, sort by citations × recency.

    Args:
        query: Search string.
        max_results: Per-backend cap.
        backends: ``{name: callable}`` where each callable has signature
            ``(query: str, max_results: int) -> list[dict]``. Built-in keys
            (``"pubmed"``, ``"semantic_scholar"``, ``"openalex"``,
            ``"europepmc"``) are recognized for the per-source count in
            the return value; any other name is reported under its raw
            key.
        cache_dir: If provided, installs a 24-hour requests cache there.

    Returns:
        ``{"query": ..., "papers": [...], "counts": {name: n}}``
    """
    if cache_dir:
        setup_cache(cache_dir)

    backends = backends or {}
    all_papers: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {}
    for name, fn in backends.items():
        print(f"\n=== Searching {name} ===", file=sys.stderr)
        try:
            papers = fn(query, max_results) or []
        except Exception as e:  # noqa: BLE001 — one bad backend shouldn't kill the search
            print(f"  {name} failed: {e}", file=sys.stderr)
            papers = []
        counts[name] = len(papers)
        all_papers.extend(papers)
        print(f"  found {len(papers)} papers", file=sys.stderr)

    unique = deduplicate_papers(all_papers)
    unique.sort(key=_sort_key)
    counts["total_unique"] = len(unique)
    return {"query": query, "papers": unique, "counts": counts}


# Functional aliases kept for the placeholder API. Each accepts an
# optional `backend` callable so the caller can plug in real HTTP code.
def search_pubmed(query: str, max_results: int = 20, backend: Optional[BackendFn] = None) -> List[Dict[str, Any]]:
    if backend is None:
        raise NotImplementedError(
            "wizard-core does not bundle a PubMed HTTP client; pass `backend=` "
            "or use search_literature() with a backends={'pubmed': ...} mapping."
        )
    return backend(query, max_results)


def search_semantic_scholar(query: str, max_results: int = 20, backend: Optional[BackendFn] = None) -> List[Dict[str, Any]]:
    if backend is None:
        raise NotImplementedError(
            "wizard-core does not bundle a Semantic Scholar HTTP client; pass `backend=` "
            "or use search_literature() with a backends={'semantic_scholar': ...} mapping."
        )
    return backend(query, max_results)
