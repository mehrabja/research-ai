"""M23 — Study characterization with provenance.

Extracts structured study fields from a Source's abstract / full
text. Every extracted field carries provenance {field, value,
source, location, confidence}.

Never fabricates: if a field cannot be extracted, it stays None and
no provenance entry is written.

IMPORTANT: apply_characterization() OVERWRITES all derived fields.
It never merges with old values. A source that no longer yields a
value (e.g. abstract changed) results in the field being cleared.
This is essential for correct recomputation semantics.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.db.models.literature import ProjectLiteratureItem
from app.db.models.source import Source
from app.domain.literature import CHARACTERIZATION_VERSION

# --- Paper type patterns -------------------------------------------------
_PAPER_TYPE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("systematic_review",
     re.compile(r"\bsystematic\s+review\b", re.IGNORECASE)),
    ("meta_analysis",
     re.compile(r"\bmeta[- ]?analy", re.IGNORECASE)),
    ("scoping_review",
     re.compile(r"\bscoping\s+review\b", re.IGNORECASE)),
    ("narrative_review",
     re.compile(r"\b(narrative|literature)\s+review\b", re.IGNORECASE)),
    ("randomized_controlled_trial",
     re.compile(
         r"\brandomi[sz]ed\s+controlled\s+trial\b|\bRCT\b",
         re.IGNORECASE,
     )),
    ("cohort_study",
     re.compile(r"\bcohort\s+study\b", re.IGNORECASE)),
    ("case_control_study",
     re.compile(r"\bcase[- ]control\b", re.IGNORECASE)),
    ("cross_sectional_study",
     re.compile(r"\bcross[- ]sectional\b", re.IGNORECASE)),
    ("case_report",
     re.compile(r"\bcase\s+report\b", re.IGNORECASE)),
    ("benchmark_paper",
     re.compile(r"\bbenchmark\b", re.IGNORECASE)),
    ("dataset_paper",
     re.compile(r"\bdataset\b", re.IGNORECASE)),
    ("protocol",
     re.compile(r"\bstudy\s+protocol\b", re.IGNORECASE)),
]

_DESIGN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("randomized_controlled_trial",
     re.compile(
         r"\brandomi[sz]ed\s+controlled\s+trial\b|\bRCT\b",
         re.IGNORECASE,
     )),
    ("cohort", re.compile(r"\bcohort\b", re.IGNORECASE)),
    ("case_control",
     re.compile(r"\bcase[- ]control\b", re.IGNORECASE)),
    ("cross_sectional",
     re.compile(r"\bcross[- ]sectional\b", re.IGNORECASE)),
    ("systematic_review",
     re.compile(r"\bsystematic\s+review\b", re.IGNORECASE)),
    ("meta_analysis",
     re.compile(r"\bmeta[- ]?analy", re.IGNORECASE)),
    ("qualitative",
     re.compile(
         r"\b(qualitative|thematic\s+analysis|"
         r"grounded\s+theory)\b",
         re.IGNORECASE,
     )),
    ("survey", re.compile(r"\b(survey|questionnaire)\b", re.IGNORECASE)),
    ("simulation", re.compile(r"\bsimulat", re.IGNORECASE)),
    ("benchmark", re.compile(r"\bbenchmark", re.IGNORECASE)),
    ("experimental",
     re.compile(
         r"\b(experiment|randomi[sz]ed)\b", re.IGNORECASE
     )),
]

_SAMPLE_SIZE_RE = re.compile(
    r"\b(?:n\s*=\s*|sample\s+size\s+of\s+|"
    r"total\s+of\s+|enrolled\s+|included\s+)"
    r"(\d{1,7})\b",
    re.IGNORECASE,
)

_POPULATION_RE = re.compile(
    r"\b(?:participants?|patients?|subjects?|cohort|children|"
    r"adults?|elderly|students?)\b[^.]{0,120}",
    re.IGNORECASE,
)

_INTERVENTION_RE = re.compile(
    r"\b(?:intervention|treatment|drug|therapy|exposure)\b"
    r"[^.]{0,120}",
    re.IGNORECASE,
)

_COMPARATOR_RE = re.compile(
    r"\b(?:compared\s+to|versus|vs\.?|control\s+group|placebo)\b"
    r"[^.]{0,120}",
    re.IGNORECASE,
)

_METHODS_RE = re.compile(
    r"((?:we\s+)?(?:used|employ(?:ed)?|applied|conducted|"
    r"performed|followed)\b[^.]{0,250}\.)",
    re.IGNORECASE,
)

_FINDINGS_RE = re.compile(
    r"((?:we\s+)?(?:found|show|demonstrate|observed|report|"
    r"concluded?|suggest(?:ed)?)\b[^.]{0,250}\.)",
    re.IGNORECASE,
)

_LIMITATIONS_RE = re.compile(
    r"(limitation[s]?[^.]{0,300}\.)",
    re.IGNORECASE | re.DOTALL,
)

_OUTCOME_TERMS = [
    "mortality", "morbidity", "accuracy", "precision",
    "recall", "f1", "auc", "sensitivity", "specificity",
    "effect size", "odds ratio", "hazard ratio", "risk ratio",
    "p-value", "confidence interval",
]

_KEYWORD_STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "these",
    "those", "into", "over", "under", "such", "than", "then",
    "also", "were", "was", "are", "has", "have", "had", "not",
    "any", "all", "but", "our", "its", "their", "there", "here",
    "which", "while", "when", "where", "what", "who", "how",
    "between", "within", "among", "about", "onto", "upon",
    "paper", "study", "research", "results", "method", "methods",
    "approach", "approaches", "data", "analysis",
}


@dataclass
class ProvenanceEntry:
    field: str
    value: object
    source_id: uuid.UUID
    location: str
    confidence: float

    def to_dict(self) -> dict:
        return {
            "field": self.field,
            "value": self.value,
            "source": f"source:{self.source_id}",
            "location": self.location,
            "confidence": self.confidence,
        }


@dataclass
class CharacterizationResult:
    paper_type_code: str | None = None
    research_design_code: str | None = None
    population: str | None = None
    sample_size: int | None = None
    intervention: str | None = None
    comparator: str | None = None
    outcomes: list[str] = field(default_factory=list)
    methods_summary: str | None = None
    findings_summary: str | None = None
    limitations_summary: str | None = None
    study_summary: str | None = None
    themes: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    provenance: list[dict] = field(default_factory=list)
    version: str = CHARACTERIZATION_VERSION


def _find_with_location(
    source: Source, pattern: re.Pattern[str]
) -> tuple[str, str] | None:
    """Return (match_text, location) searching abstract first, then
    full text, so provenance location is accurate."""
    if source.abstract:
        m = pattern.search(source.abstract)
        if m:
            return m.group(0).strip(), "abstract"
    if source.full_text:
        m = pattern.search(source.full_text)
        if m:
            return m.group(0).strip(), "full_text"
    return None


def _extract_paper_type(text: str) -> str | None:
    for code, pattern in _PAPER_TYPE_PATTERNS:
        if pattern.search(text):
            return code
    return None


def _extract_design(text: str) -> str | None:
    for code, pattern in _DESIGN_PATTERNS:
        if pattern.search(text):
            return code
    return None


def _extract_sample_size(text: str) -> int | None:
    m = _SAMPLE_SIZE_RE.search(text)
    if not m:
        return None
    try:
        n = int(m.group(1))
    except ValueError:
        return None
    if n <= 0 or n > 10_000_000:
        return None
    return n


def _extract_outcomes(text: str) -> list[str]:
    low = text.lower()
    return sorted({t for t in _OUTCOME_TERMS if t in low})


def _extract_keywords(text: str, *, limit: int = 20) -> list[str]:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z\-]{3,}", text.lower())
    counts: dict[str, int] = {}
    for t in tokens:
        if t in _KEYWORD_STOPWORDS:
            continue
        counts[t] = counts.get(t, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [w for w, _ in ranked[:limit]]


def _extract_themes(text: str, *, limit: int = 8) -> list[str]:
    tokens = [
        w for w in re.findall(r"[a-zA-Z][a-zA-Z\-]{3,}", text.lower())
        if w not in _KEYWORD_STOPWORDS
    ]
    grams: dict[str, int] = {}
    for i in range(len(tokens) - 1):
        g = f"{tokens[i]} {tokens[i+1]}"
        grams[g] = grams.get(g, 0) + 1
    ranked = sorted(grams.items(), key=lambda kv: (-kv[1], kv[0]))
    return [g for g, c in ranked if c >= 2][:limit]


def characterize_literature_item(
    db: Session,
    *,
    item: ProjectLiteratureItem,
    source: Source,
) -> CharacterizationResult:
    abstract = source.abstract or ""
    full = source.full_text or ""
    combined = "\n".join(filter(None, [abstract, full]))
    if not combined.strip():
        return CharacterizationResult()

    result = CharacterizationResult()
    prov = result.provenance

    # --- paper type -------------------------------------------------
    pt, pt_loc = None, None
    if abstract:
        pt = _extract_paper_type(abstract)
        if pt:
            pt_loc = "abstract"
    if not pt and full:
        pt = _extract_paper_type(full)
        if pt:
            pt_loc = "full_text"
    if pt:
        result.paper_type_code = pt
        prov.append(
            ProvenanceEntry(
                "paper_type_code", pt, source.id,
                pt_loc or "metadata", 0.6,
            ).to_dict()
        )

    # --- research design -------------------------------------------
    rd, rd_loc = None, None
    if abstract:
        rd = _extract_design(abstract)
        if rd:
            rd_loc = "abstract"
    if not rd and full:
        rd = _extract_design(full)
        if rd:
            rd_loc = "full_text"
    if rd:
        result.research_design_code = rd
        prov.append(
            ProvenanceEntry(
                "research_design_code", rd, source.id,
                rd_loc or "metadata", 0.6,
            ).to_dict()
        )

    # --- sample size -----------------------------------------------
    n, n_loc = None, None
    if abstract:
        n = _extract_sample_size(abstract)
        if n is not None:
            n_loc = "abstract"
    if n is None and full:
        n = _extract_sample_size(full)
        if n is not None:
            n_loc = "full_text"
    if n is not None:
        result.sample_size = n
        prov.append(
            ProvenanceEntry(
                "sample_size", n, source.id,
                n_loc or "metadata", 0.75,
            ).to_dict()
        )

    # --- population / intervention / comparator -------------------
    pop = _find_with_location(source, _POPULATION_RE)
    if pop:
        result.population = pop[0][:300]
        prov.append(
            ProvenanceEntry(
                "population", result.population, source.id, pop[1], 0.5
            ).to_dict()
        )

    inter = _find_with_location(source, _INTERVENTION_RE)
    if inter:
        result.intervention = inter[0][:300]
        prov.append(
            ProvenanceEntry(
                "intervention", result.intervention,
                source.id, inter[1], 0.5,
            ).to_dict()
        )

    comp = _find_with_location(source, _COMPARATOR_RE)
    if comp:
        result.comparator = comp[0][:300]
        prov.append(
            ProvenanceEntry(
                "comparator", result.comparator,
                source.id, comp[1], 0.5,
            ).to_dict()
        )

    # --- outcomes ---------------------------------------------------
    outcomes = _extract_outcomes(combined)
    if outcomes:
        result.outcomes = outcomes
        prov.append(
            ProvenanceEntry(
                "outcomes", outcomes, source.id, "combined", 0.5
            ).to_dict()
        )

    # --- limitations ------------------------------------------------
    lim = _find_with_location(source, _LIMITATIONS_RE)
    if lim:
        result.limitations_summary = lim[0][:500]
        prov.append(
            ProvenanceEntry(
                "limitations_summary", result.limitations_summary,
                source.id, lim[1], 0.5,
            ).to_dict()
        )

    # --- methods summary -------------------------------------------
    methods_hit = _find_with_location(source, _METHODS_RE)
    if methods_hit:
        result.methods_summary = methods_hit[0][:500]
        prov.append(
            ProvenanceEntry(
                "methods_summary", result.methods_summary,
                source.id, methods_hit[1], 0.6,
            ).to_dict()
        )

    # --- findings summary ------------------------------------------
    findings_source = abstract or full
    if findings_source:
        f = _find_with_location(source, _FINDINGS_RE)
        if f:
            result.findings_summary = f[0][:500]
            prov.append(
                ProvenanceEntry(
                    "findings_summary", result.findings_summary,
                    source.id, f[1], 0.6,
                ).to_dict()
            )

    # --- study summary (abstract-first 500 chars) ------------------
    if abstract:
        result.study_summary = abstract[:500]
        prov.append(
            ProvenanceEntry(
                "study_summary", result.study_summary,
                source.id, "abstract", 0.9,
            ).to_dict()
        )
    elif full:
        result.study_summary = full[:500]
        prov.append(
            ProvenanceEntry(
                "study_summary", result.study_summary,
                source.id, "full_text", 0.9,
            ).to_dict()
        )

    # --- themes / keywords -----------------------------------------
    themes = _extract_themes(combined)
    if themes:
        result.themes = themes
    keywords = _extract_keywords(combined)
    if keywords:
        result.keywords = keywords

    return result


def apply_characterization(
    db: Session,
    *,
    item: ProjectLiteratureItem,
    source: Source,
) -> CharacterizationResult:
    """Overwrite ALL derived fields with the fresh extraction.

    No `result or item` merge: a field that is not extractable from
    the current source is cleared so stale data never survives a
    re-run. User-facing fields (screening_status, manual_override*,
    analysis_status) are owned by other code paths and are not
    touched here.

    Does NOT commit — caller owns transaction.
    """
    result = characterize_literature_item(
        db, item=item, source=source
    )
    item.paper_type_code = result.paper_type_code
    item.research_design_code = result.research_design_code
    item.population = result.population
    item.sample_size = result.sample_size
    item.intervention = result.intervention
    item.comparator = result.comparator
    item.outcomes = result.outcomes or None
    item.methods_summary = result.methods_summary
    item.findings_summary = result.findings_summary
    item.limitations_summary = result.limitations_summary
    item.study_summary = result.study_summary
    item.themes = result.themes or None
    item.keywords = result.keywords or None
    item.extraction_provenance = result.provenance or None
    db.flush()
    return result


__all__ = [
    "CharacterizationResult",
    "ProvenanceEntry",
    "apply_characterization",
    "characterize_literature_item",
]
