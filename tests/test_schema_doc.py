from graph import schema_doc as s


def test_vocab_present():
    assert s.LOBS == ["CB", "CM", "Wealth", "P&BB"]
    assert "US Midwest" in s.US_REGIONS
    assert set(s.INDUSTRIES_OF_INTEREST) == {"franchisee", "auto_dealer", "equipment"}


def test_schema_text_mentions_core_tables():
    for tbl in ["Company", "Person", "Region", "LineOfBusiness",
                "COMPANY_HAS_RELATIONSHIP", "PERSON_HAS_RELATIONSHIP",
                "EXECUTIVE_OF", "EMPLOYED_BY",
                "COMPANY_LOCATED_IN", "PERSON_LOCATED_IN"]:
        assert tbl in s.SCHEMA_TEXT
