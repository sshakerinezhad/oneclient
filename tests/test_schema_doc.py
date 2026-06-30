from graph import schema_doc as s


def test_vocab_present():
    assert s.LOBS == ["CB", "CM", "Wealth", "P&BB"]
    assert "US Midwest" in s.US_REGIONS
    assert set(s.INDUSTRIES_OF_INTEREST) == {"franchisee", "auto_dealer", "equipment"}


def test_schema_text_mentions_core_tables():
    for tbl in ["Company", "Person", "Region", "LineOfBusiness",
                "HAS_RELATIONSHIP", "EXECUTIVE_OF", "EMPLOYED_BY", "LOCATED_IN"]:
        assert tbl in s.SCHEMA_TEXT
