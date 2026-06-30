"""Generate all staged CSVs from fixtures + population."""
import csv
from pathlib import Path

from generate.fixtures import Fixtures, build_fixtures
from generate.population import build_population
from graph.schema_doc import ALL_REGIONS, LOBS, US_REGIONS


def main(staged_dir: str = "data/staged") -> None:
    """Build fixtures, run population, write 10 CSVs to staged_dir."""
    out = Path(staged_dir)
    out.mkdir(parents=True, exist_ok=True)

    fx = build_fixtures()
    build_population(fx)

    _write_companies(out, fx)
    _write_persons(out, fx)
    _write_regions(out)
    _write_lobs(out)
    _write_rel_company_lob(out, fx)
    _write_rel_person_lob(out, fx)
    _write_rel_executive_of(out, fx)
    _write_rel_employed_by(out, fx)
    _write_rel_company_located_in(out, fx)
    _write_rel_person_located_in(out, fx)

    print(f"Generated {len(fx.companies)} companies, {len(fx.persons)} persons -> {out}")


# ---------------------------------------------------------------------------
# Node writers
# ---------------------------------------------------------------------------

def _write_companies(out: Path, fx: Fixtures) -> None:
    with open(out / "companies.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerow([
            "ecif_id", "name", "country", "region", "industry",
            "employee_count", "revenue", "net_income", "rwa", "roe",
            "lending_balance", "deposit_balance",
        ])
        for c in fx.companies:
            writer.writerow([
                c.ecif_id, c.name, c.country, c.region, c.industry,
                c.employee_count, c.revenue, c.net_income, c.rwa, c.roe,
                c.lending_balance, c.deposit_balance,
            ])


def _write_persons(out: Path, fx: Fixtures) -> None:
    with open(out / "persons.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["ecif_id", "name", "country", "region", "customer_type"])
        for p in fx.persons:
            writer.writerow([p.ecif_id, p.name, p.country, p.region, p.customer_type])


def _write_regions(out: Path) -> None:
    with open(out / "regions.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["name", "country"])
        for region in ALL_REGIONS:
            country = "US" if region in US_REGIONS else "CA"
            writer.writerow([region, country])


def _write_lobs(out: Path) -> None:
    with open(out / "lob.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["name"])
        for lob in LOBS:
            writer.writerow([lob])


# ---------------------------------------------------------------------------
# Relationship writers
# ---------------------------------------------------------------------------

def _write_rel_company_lob(out: Path, fx: Fixtures) -> None:
    with open(out / "rel_company_lob.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["company_ecif_id", "lob_name", "revenue", "lending", "deposit"])
        for r in fx.rel_company_lob:
            writer.writerow([r.src, r.lob, r.revenue, r.lending, r.deposit])


def _write_rel_person_lob(out: Path, fx: Fixtures) -> None:
    with open(out / "rel_person_lob.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["person_ecif_id", "lob_name", "revenue", "lending", "deposit"])
        for r in fx.rel_person_lob:
            writer.writerow([r.src, r.lob, r.revenue, r.lending, r.deposit])


def _write_rel_executive_of(out: Path, fx: Fixtures) -> None:
    with open(out / "rel_executive_of.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["person_ecif_id", "company_ecif_id", "title"])
        for e in fx.executive_of:
            writer.writerow([e.src, e.dst, e.title])


def _write_rel_employed_by(out: Path, fx: Fixtures) -> None:
    with open(out / "rel_employed_by.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["person_ecif_id", "company_ecif_id"])
        for e in fx.employed_by:
            writer.writerow([e.src, e.dst])


def _write_rel_company_located_in(out: Path, fx: Fixtures) -> None:
    """Derived from company.region — one edge per company."""
    with open(out / "rel_company_located_in.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["company_ecif_id", "region_name"])
        for c in fx.companies:
            writer.writerow([c.ecif_id, c.region])


def _write_rel_person_located_in(out: Path, fx: Fixtures) -> None:
    """Derived from person.region — one edge per person."""
    with open(out / "rel_person_located_in.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["person_ecif_id", "region_name"])
        for p in fx.persons:
            writer.writerow([p.ecif_id, p.region])


if __name__ == "__main__":
    main()
