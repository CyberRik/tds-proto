"""Deterministic TDS rules: Act selection, rate lookup, tax.

Nothing here is decided by the LLM. Every row cites a
source, holds both Acts' references, and says whether it
has been verified against a primary source.
"""
from dataclasses import dataclass
from datetime import date

NEW_ACT_START = date(2026, 4, 1)
RULES_VERSION = "2026-11-02"

LABELS = [
    "contract_work",
    "professional_fees",
    "technical_services",
    "rent_plant_machinery",
    "rent_land_building",
    "commission",
]

SRC_ACT = ("Income-tax Act 2025 s.393(1) Table, as "
           "amended by Finance Act 2026, pp.467-472")
SRC_FAQ = ("incometax.gov.in TDS compliance FAQ 2 and 3 "
           "(Act by earlier of credit/payment; rates "
           "retained); " + SRC_ACT)


@dataclass(frozen=True)
class Rule:
    label: str
    payee: str          # "individual", "other", "any"
    old_ref: str        # Income-tax Act, 1961
    new_ref: str        # Income-tax Act, 2025
    new_ref_verified: bool
    rate: float
    single_limit: int   # per payment (0 = none)
    annual_limit: int   # per year aggregate (0 = none)
    monthly_limit: int  # per month (0 = none)
    source: str


RULES = [
    # Payer is assumed to be a designated/specified person
    # (s.402(11), s.402(37)), e.g. a company.
    # IT Dept FAQ example: contractor -> 393(1) Tbl 6(i)
    Rule("contract_work", "individual", "194C",
         "393(1) Table Sl. 6(i)", True,
         0.01, 30_000, 100_000, 0, SRC_FAQ),
    Rule("contract_work", "other", "194C",
         "393(1) Table Sl. 6(i)", True,
         0.02, 30_000, 100_000, 0, SRC_FAQ),
    Rule("professional_fees", "any", "194J(b)",
         "393(1) Table Sl. 6(iii)", True,
         0.10, 0, 50_000, 0, SRC_ACT),
    Rule("technical_services", "any", "194J(a)",
         "393(1) Table Sl. 6(iii)", True,
         0.02, 0, 50_000, 0, SRC_ACT),
    Rule("rent_plant_machinery", "any", "194I(a)",
         "393(1) Table Sl. 2(ii)", True,
         0.02, 0, 0, 50_000, SRC_ACT),
    Rule("rent_land_building", "any", "194I(b)",
         "393(1) Table Sl. 2(ii)", True,
         0.10, 0, 0, 50_000, SRC_ACT),
    Rule("commission", "any", "194H",
         "393(1) Table Sl. 1(ii)", True,
         0.02, 0, 20_000, 0, SRC_ACT),
]


def governing_act(credit: date, payment: date) -> str:
    """TDS follows the earlier of credit or payment."""
    trigger = min(credit, payment)
    return "2025" if trigger >= NEW_ACT_START else "1961"


def find_rule(label: str, payee: str) -> Rule:
    for r in RULES:
        if r.label == label and r.payee in (payee, "any"):
            return r
    raise KeyError(f"no rule for {label}/{payee}")


def compute(label, payee, amount, ytd_before,
            credit, payment, ytd_taxed=0):
    """Return the full, explainable TDS decision.

    ytd_taxed is the part of ytd_before that already bore
    TDS, e.g. an earlier sum above the single-sum limit.
    """
    rule = find_rule(label, payee)
    act = governing_act(credit, payment)
    ytd_after = ytd_before + amount
    base = amount

    if rule.monthly_limit:
        # monthly rent: amount is one month's rent
        applies = amount > rule.monthly_limit
    else:
        over_single = (rule.single_limit
                       and amount > rule.single_limit)
        over_annual = (rule.annual_limit
                       and ytd_after > rule.annual_limit)
        applies = bool(over_single or over_annual)
        # s.393(1)(a): tax is on the entire amount once the
        # aggregate is crossed, so catch up earlier sums on
        # the invoice that crosses it.
        if over_annual and ytd_before <= rule.annual_limit:
            base = ytd_after - ytd_taxed

    tds = round(base * rule.rate) if applies else 0
    ref = rule.old_ref if act == "1961" else rule.new_ref
    verified = act == "1961" or rule.new_ref_verified
    return {
        "act": act,
        "section": ref,
        "section_verified": verified,
        "rate": rule.rate,
        "threshold_crossed": applies,
        "tds_base": base if applies else 0,
        "tds": tds,
        "source": rule.source,
        "rules_version": RULES_VERSION,
    }


def exposure(chosen, alternatives, payee, amount,
             ytd_before, credit, payment, ytd_taxed=0):
    """Rupees at risk if a plausible alternative is right.

    = max(TDS under alternative) - TDS under chosen,
    floored at zero. Pure arithmetic, no model involved.
    """
    base = compute(chosen, payee, amount, ytd_before,
                   credit, payment, ytd_taxed)["tds"]
    worst = base
    for alt in alternatives:
        if alt not in LABELS:
            continue
        t = compute(alt, payee, amount, ytd_before,
                    credit, payment, ytd_taxed)["tds"]
        worst = max(worst, t)
    return worst - base
