"""Curated inventory of scientific connectors considered for MCP integration.

This is descriptive metadata only. Entries are intentionally non-executable until
an authenticated, workspace-scoped adapter and its policy tests are implemented.
"""
from __future__ import annotations

from typing import Any

# Inventory aligned with the 48 connector IDs in Parsian's connector-builtins
# catalog. Do not infer a live endpoint or credential contract from this list.
_GROUPS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("literature_datasets", "Literature and datasets", (
        "europepmc", "research-datasets", "literature", "pubmed", "biorxiv",
        "research-resources", "zenodo",
    )),
    ("genes_pathways", "Genes and pathways", (
        "chea3", "biodbnet", "ctd", "kegg", "wikipathways", "encori", "monarch",
        "alliance", "pathway-commons", "genes", "genomes", "variants",
        "expression", "regulation", "biomart",
    )),
    ("clinical_biomedical", "Clinical and biomedical data", (
        "tcia", "pdc", "biosamples", "rxnorm", "dailymed", "orphadata", "iedb",
        "clinical-trials", "clinical-genomics", "human-genetics", "cancer-models", "gdc",
    )),
    ("chemistry_compounds", "Chemistry and compounds", (
        "chemistry", "molecule", "chembl", "drug-regulatory", "zinc",
    )),
    ("protein_structure", "Protein and structure", (
        "structures", "hmmer", "interproscan", "protein-annotation",
    )),
    ("cell_omics", "Cell and omics data", (
        "rna", "omics-archives", "cellxgene-discover", "cellosaurus", "cellguide",
    )),
)

_DISPLAY_NAMES = {
    "europepmc": "Europe PMC",
    "research-datasets": "Research Datasets",
    "chea3": "ChEA3",
    "biodbnet": "BioDBnet",
    "ctd": "Comparative Toxicogenomics Database (CTD)",
    "tcia": "The Cancer Imaging Archive (TCIA)",
    "kegg": "KEGG",
    "rxnorm": "RxNorm",
    "dailymed": "DailyMed",
    "biosamples": "BioSamples",
    "wikipathways": "WikiPathways",
    "orphadata": "Orphadata",
    "encori": "ENCORI",
    "pdc": "Proteomic Data Commons (PDC)",
    "iedb": "Immune Epitope Database (IEDB)",
    "monarch": "Monarch Initiative",
    "alliance": "Alliance of Genome Resources",
    "chemistry": "Chemistry",
    "literature": "Literature",
    "molecule": "Molecule",
    "pubmed": "PubMed",
    "genes": "Genes",
    "pathway-commons": "Pathway Commons",
    "genomes": "Genomes",
    "variants": "Variants",
    "clinical-trials": "ClinicalTrials.gov",
    "clinical-genomics": "Clinical Genomics",
    "structures": "Structures",
    "chembl": "ChEMBL",
    "biorxiv": "bioRxiv",
    "drug-regulatory": "Drug Regulatory",
    "human-genetics": "Human Genetics",
    "expression": "Expression",
    "hmmer": "HMMER",
    "interproscan": "InterProScan",
    "protein-annotation": "Protein Annotation",
    "cancer-models": "Cancer Models",
    "gdc": "Genomic Data Commons (GDC)",
    "rna": "RNA",
    "omics-archives": "Omics Archives",
    "cellxgene-discover": "CELLxGENE Discover",
    "cellosaurus": "Cellosaurus",
    "cellguide": "CellGuide",
    "regulation": "Regulation",
    "research-resources": "Research Resources",
    "biomart": "BioMart",
    "zinc": "ZINC",
    "zenodo": "Zenodo",
}

_CATEGORY_DESCRIPTIONS = {
    "literature_datasets": "literature, preprint, dataset, or research-resource discovery",
    "genes_pathways": "gene, genome, variant, pathway, expression, or regulatory information",
    "clinical_biomedical": "clinical, translational, disease, sample, or biomedical reference information",
    "chemistry_compounds": "chemical, compound, drug, or small-molecule reference information",
    "protein_structure": "protein family, annotation, sequence, or structure information",
    "cell_omics": "cell-line, single-cell, RNA, or omics reference information",
}


def list_scientific_connectors(*, project_bound: bool = True) -> list[dict[str, Any]]:
    """Return the non-executable connector catalog for project-bound contexts."""
    if not project_bound:
        return []

    entries: list[dict[str, Any]] = []
    for category, category_name, connector_ids in _GROUPS:
        for connector_id in connector_ids:
            entries.append(
                {
                    "id": connector_id,
                    "display_name": _DISPLAY_NAMES[connector_id],
                    "category": category,
                    "category_name": category_name,
                    "description": (
                        "Planned connector for "
                        + _CATEGORY_DESCRIPTIONS[category]
                        + "."
                    ),
                    "integration_status": "catalog_only",
                    "transport": "mcp_candidate",
                    "requires_approval": True,
                    "executable": False,
                }
            )
    return entries


def get_scientific_connector(connector_id: str) -> dict[str, Any] | None:
    """Resolve one catalog entry without implying that it is executable."""
    normalized = connector_id.strip().lower() if isinstance(connector_id, str) else ""
    for entry in list_scientific_connectors():
        if entry["id"] == normalized:
            return entry
    return None


__all__ = ["get_scientific_connector", "list_scientific_connectors"]
