from app.services.research_planning import templates


def test_known_paper_types_have_deterministic_template():
    for pt in templates.known_paper_types():
        a = templates.select_template(pt)
        b = templates.select_template(pt)
        assert a.paper_type_code == pt
        assert len(a.sections) > 0
        assert [s.key for s in a.sections] == [s.key for s in b.sections]
        assert [s.section_type for s in a.sections] == [
            s.section_type for s in b.sections
        ]
        keys = [s.key for s in a.sections]
        assert len(keys) == len(set(keys))


def test_unknown_paper_type_falls_back_to_generic():
    t = templates.select_template("does_not_exist")
    assert t.paper_type_code == "unknown"


def test_none_paper_type_falls_back_to_generic():
    t = templates.select_template(None)
    assert t.paper_type_code == "unknown"
