"""Tests for the deterministic parts (no LLM needed).

Classifier outputs below are hand-written fixtures,
not real model responses.
"""
from datetime import date as D

import rules
from classify import (evidence_coverage, evidence_ok,
                      parse_json)
from router import route
from run import decide, history_for


def test_act_by_earlier_of_credit_or_payment():
    # credited March, paid April -> old Act
    assert rules.governing_act(
        D(2026, 3, 28), D(2026, 4, 6)) == "1961"
    # advance paid March, credited April -> old Act
    assert rules.governing_act(
        D(2026, 4, 2), D(2026, 3, 30)) == "1961"
    assert rules.governing_act(
        D(2026, 4, 1), D(2026, 4, 1)) == "2025"


def test_section_reference_switches():
    old = rules.compute("contract_work", "other", 85000,
                        0, D(2026, 3, 31), D(2026, 4, 5))
    new = rules.compute("contract_work", "other", 85000,
                        0, D(2026, 4, 30), D(2026, 5, 5))
    assert old["section"] == "194C"
    assert new["section"].startswith("393(1)")
    assert old["tds"] == new["tds"] == 1700


def test_thresholds():
    # 12k single, 32k aggregate: below both 194C limits
    r = rules.compute("contract_work", "individual",
                      12000, 20000, D(2026, 9, 2),
                      D(2026, 9, 2))
    assert r["tds"] == 0
    # aggregate crosses 1L: s.393(1)(a) entire amount,
    # so the earlier 95k is caught up
    r = rules.compute("contract_work", "individual",
                      12000, 95000, D(2026, 9, 2),
                      D(2026, 9, 2))
    assert r["tds"] == 1070
    # part of the earlier 95k already bore TDS
    r = rules.compute("contract_work", "individual",
                      12000, 95000, D(2026, 9, 2),
                      D(2026, 9, 2), ytd_taxed=40000)
    assert r["tds"] == 670
    # already past 1L: only the new invoice
    r = rules.compute("contract_work", "individual",
                      12000, 107000, D(2026, 9, 2),
                      D(2026, 9, 2))
    assert r["tds"] == 120
    # single sum over 30k, aggregate under 1L: only that sum
    r = rules.compute("contract_work", "individual",
                      40000, 20000, D(2026, 9, 2),
                      D(2026, 9, 2))
    assert r["tds"] == 400


def test_exposure_contract_vs_technical_is_zero():
    # both 2% for a company payee: label dispute,
    # no rupee difference
    e = rules.exposure("contract_work",
                       ["technical_services"], "other",
                       480000, 0, D(2026, 7, 1),
                       D(2026, 7, 10))
    assert e == 0


def test_exposure_contract_vs_professional():
    e = rules.exposure("contract_work",
                       ["professional_fees"], "other",
                       180000, 0, D(2026, 4, 10),
                       D(2026, 4, 15))
    assert e == 18000 - 3600


def test_evidence_check_catches_invented_quote():
    text = "AMC for 14 split ACs incl. spares"
    assert evidence_ok(text, ["14 split ACs"])
    assert not evidence_ok(text, ["MRI calibration"])
    assert not evidence_ok(text, [])


def test_bad_model_output_fails_closed():
    assert parse_json("sorry, I can't")["label"] \
        == "unclear"
    assert parse_json('{"label": "194J"}')["label"] \
        == "unclear"


def test_history_ignores_auto_and_stale():
    h = [{"vendor": "A", "label": "x",
          "approved_by": "auto",
          "rules_version": rules.RULES_VERSION},
         {"vendor": "B", "label": "y",
          "approved_by": "CA",
          "rules_version": "2025-04-01"}]
    assert history_for("A", h) is None
    assert history_for("B", h) is None


def test_history_can_only_add_a_flag():
    run = {"label": "commission", "confidence": "high",
           "alternatives": []}
    dec = {"section_verified": True}
    clean = route(run, run, True, dec, 0, None)
    assert clean["would_auto_post"]
    flagged = route(run, run, True, dec, 0,
                    "contract_work")
    assert not flagged["would_auto_post"]
    # shadow mode: still goes to CA either way
    assert clean["route"] == "ca_review"


def test_one_run_mentioning_a_label_is_not_contested():
    r1 = {"label": "contract_work", "confidence": "high",
          "alternatives": []}
    r2 = {**r1, "alternatives": ["technical_services"]}
    dec = {"section_verified": True}
    assert route(r1, r2, True, dec, 0)["would_auto_post"]
    assert not route(r2, r2, True, dec,
                     0)["would_auto_post"]


def test_exposure_counts_alternatives_from_both_runs():
    inv = {"vendor": "V", "payee": "other", "text": "x",
           "amount": 180000, "ytd_before": 0,
           "credit": "2026-04-10", "payment": "2026-04-15"}
    r1 = {"label": "contract_work", "alternatives": [],
          "evidence": ["x"], "confidence": "high"}
    r2 = {**r1, "alternatives": ["professional_fees"]}
    out = decide(inv, r1, r2, [])
    assert out["exposure"] == 18000 - 3600
    # a one-run mention still escalates when money is at risk
    assert not out["routing"]["would_auto_post"]


def test_evidence_coverage():
    text = "AMC for 14 split ACs"
    assert evidence_coverage(text, [text]) == 1.0
    assert evidence_coverage(text, ["AMC"]) == 0.15


def test_new_act_rows_match_the_table():
    refs = {r.label: r.new_ref for r in rules.RULES}
    assert refs["professional_fees"].endswith("Sl. 6(iii)")
    assert refs["technical_services"].endswith("Sl. 6(iii)")
    assert refs["rent_plant_machinery"].endswith("Sl. 2(ii)")
    assert refs["rent_land_building"].endswith("Sl. 2(ii)")
    assert refs["commission"].endswith("Sl. 1(ii)")
    assert all(r.new_ref_verified for r in rules.RULES)
