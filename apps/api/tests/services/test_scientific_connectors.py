from __future__ import annotations

from app.services.scientific_connectors import (
    get_scientific_connector,
    list_scientific_connectors,
)


EXPECTED_CONNECTOR_IDS = {
    "europepmc", "research-datasets", "chea3", "biodbnet", "ctd", "tcia",
    "kegg", "rxnorm", "dailymed", "biosamples", "wikipathways", "orphadata",
    "encori", "pdc", "iedb", "monarch", "alliance", "chemistry", "literature",
    "molecule", "pubmed", "genes", "pathway-commons", "genomes", "variants",
    "clinical-trials", "clinical-genomics", "structures", "chembl", "biorxiv",
    "drug-regulatory", "human-genetics", "expression", "hmmer", "interproscan",
    "protein-annotation", "cancer-models", "gdc", "rna", "omics-archives",
    "cellxgene-discover", "cellosaurus", "cellguide", "regulation",
    "research-resources", "biomart", "zinc", "zenodo",
}


def test_connector_catalog_contains_the_expected_48_unique_ids() -> None:
    entries = list_scientific_connectors()

    assert len(entries) == 48
    assert {entry["id"] for entry in entries} == EXPECTED_CONNECTOR_IDS
    assert len({entry["id"] for entry in entries}) == len(entries)


def test_catalog_entries_are_explicitly_non_executable_until_integrated() -> None:
    entries = list_scientific_connectors()

    assert all(entry["integration_status"] == "catalog_only" for entry in entries)
    assert all(entry["transport"] == "mcp_candidate" for entry in entries)
    assert all(entry["requires_approval"] is True for entry in entries)
    assert all(entry["executable"] is False for entry in entries)


def test_non_project_bound_context_receives_no_connector_catalog() -> None:
    assert list_scientific_connectors(project_bound=False) == []


def test_connector_lookup_is_case_insensitive_and_does_not_enable_execution() -> None:
    entry = get_scientific_connector("EUROPEPMC")

    assert entry is not None
    assert entry["display_name"] == "Europe PMC"
    assert entry["executable"] is False
    assert get_scientific_connector("not-a-connector") is None
