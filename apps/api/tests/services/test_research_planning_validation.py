from types import SimpleNamespace

from app.services.research_planning import validation


def _sec(key, order, title="T", required=True, wb=100):
    return SimpleNamespace(
        section_key=key, display_order=order, title=title,
        purpose="p", required=required, word_budget=wb,
    )


def _req(key, section_key):
    return SimpleNamespace(
        requirement_key=key, section_key=section_key,
    )


def test_valid_structure():
    secs = [_sec("a", 0), _sec("b", 1)]
    reqs = [_req("r1", "a"), _req("r2", "b")]
    budget = {"section_allocations": {"a": 0.5, "b": 0.5}}
    v = validation.validate_plan_structure(
        sections=secs, requirements=reqs, budget=budget,
        dependency_edges=[("a", "b")],
        plan_section_key_of=lambda s: s.section_key,
        category_resolved=True,
    )
    assert v.valid()
    assert v.score == 1.0


def test_empty_sections():
    v = validation.validate_plan_structure(
        sections=[], requirements=[], budget={},
        dependency_edges=[],
        plan_section_key_of=lambda s: s.section_key,
        category_resolved=True,
    )
    assert not v.valid()
    assert any("no sections" in e for e in v.errors)


def test_duplicate_keys():
    secs = [_sec("a", 0), _sec("a", 1)]
    v = validation.validate_plan_structure(
        sections=secs, requirements=[_req("r1", "a")],
        budget={"section_allocations": {"a": 1.0}},
        dependency_edges=[],
        plan_section_key_of=lambda s: s.section_key,
        category_resolved=True,
    )
    assert not v.valid()
    assert any("duplicate" in e for e in v.errors)


def test_non_continuous_order():
    secs = [_sec("a", 0), _sec("b", 3)]
    v = validation.validate_plan_structure(
        sections=secs,
        requirements=[_req("r1", "a"), _req("r2", "b")],
        budget={"section_allocations": {"a": 0.5, "b": 0.5}},
        dependency_edges=[],
        plan_section_key_of=lambda s: s.section_key,
        category_resolved=True,
    )
    assert not v.valid()
    assert any("continuous" in e for e in v.errors)


def test_required_section_missing_requirement():
    secs = [_sec("a", 0, required=True)]
    v = validation.validate_plan_structure(
        sections=secs, requirements=[],
        budget={"section_allocations": {"a": 1.0}},
        dependency_edges=[],
        plan_section_key_of=lambda s: s.section_key,
        category_resolved=True,
    )
    assert not v.valid()
    assert any("no evidence requirements" in e for e in v.errors)


def test_missing_allocation():
    secs = [_sec("a", 0)]
    v = validation.validate_plan_structure(
        sections=secs,
        requirements=[_req("r1", "a")],
        budget={"section_allocations": {}},
        dependency_edges=[],
        plan_section_key_of=lambda s: s.section_key,
        category_resolved=True,
    )
    assert not v.valid()
    assert any("missing budget allocation" in e for e in v.errors)


def test_cycle_detected():
    secs = [_sec("a", 0), _sec("b", 1)]
    v = validation.validate_plan_structure(
        sections=secs,
        requirements=[_req("r1", "a"), _req("r2", "b")],
        budget={"section_allocations": {"a": 0.5, "b": 0.5}},
        dependency_edges=[("a", "b"), ("b", "a")],
        plan_section_key_of=lambda s: s.section_key,
        category_resolved=True,
    )
    assert not v.valid()
    assert any("cycle" in e.lower() for e in v.errors)
