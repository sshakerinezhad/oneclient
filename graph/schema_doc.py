LOBS = ["CB", "CM", "Wealth", "P&BB"]
US_REGIONS = ["US Midwest", "US Northeast", "US South", "US West"]
CA_REGIONS = ["Ontario", "Quebec", "Prairies", "BC", "Atlantic"]
ALL_REGIONS = US_REGIONS + CA_REGIONS
INDUSTRIES_OF_INTEREST = ["franchisee", "auto_dealer", "equipment"]
OTHER_INDUSTRIES = ["manufacturing", "retail", "healthcare", "tech", "logistics", "real_estate"]

SCHEMA_TEXT = """
GRAPH SCHEMA (kuzu)

NODES
  Company(ecif_id STRING PK, name STRING, country STRING, region STRING,
          industry STRING, employee_count INT64, revenue DOUBLE, net_income DOUBLE,
          rwa DOUBLE, roe DOUBLE, lending_balance DOUBLE, deposit_balance DOUBLE)
  Person(ecif_id STRING PK, name STRING, country STRING, region STRING, customer_type STRING)
  Region(name STRING PK, country STRING)
  LineOfBusiness(name STRING PK)        // one of: CB, CM, Wealth, P&BB

RELATIONSHIPS
  COMPANY_HAS_RELATIONSHIP (Company->LineOfBusiness)
        {revenue DOUBLE, lending DOUBLE, deposit DOUBLE}
  PERSON_HAS_RELATIONSHIP  (Person->LineOfBusiness)
        {revenue DOUBLE, lending DOUBLE, deposit DOUBLE}
  EXECUTIVE_OF (Person->Company) {title STRING}
  EMPLOYED_BY  (Person->Company)            // bank-at-work signal
  COMPANY_LOCATED_IN (Company->Region)
  PERSON_LOCATED_IN  (Person->Region)

NOTES
  - A company "has a CB/CM/Wealth relationship" == a COMPANY_HAS_RELATIONSHIP edge to that LineOfBusiness.
  - A person "has a P&BB/Wealth relationship" == a PERSON_HAS_RELATIONSHIP edge to that LineOfBusiness.
  - Company.industry interesting values: franchisee, auto_dealer, equipment.
  - Regions: US Midwest/Northeast/South/West; Ontario, Quebec, Prairies, BC, Atlantic.
"""
