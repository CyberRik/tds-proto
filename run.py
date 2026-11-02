"""Run the prototype over the synthetic invoices.

  python run.py              baseline + full LLM pipeline
  python run.py --baseline   keyword baseline only (no key)
  python run.py --replay     re-apply code to the model
                             outputs in audit_log.jsonl
                             (no key, no API calls)
  python run.py --resume     reuse saved outputs, call the
                             model only for missing invoices

Writes results.md (table) and audit_log.jsonl.
"""
import json
import re
import statistics
import sys
import time
from datetime import date, datetime

import rules
from classify import (keyword_baseline, llm_classify,
                      evidence_ok, evidence_coverage)
from router import route


def d(s):
    return date.fromisoformat(s)


def history_for(vendor, history):
    """Only CA-approved entries made under the CURRENT
    rules version count. Auto-posted or stale entries are
    ignored, so the system never learns from itself."""
    for h in history:
        if (h["vendor"] == vendor
                and h["approved_by"] == "CA"
                and h["rules_version"]
                == rules.RULES_VERSION):
            return h["label"]
    return None


def decide(inv, r1, r2, history):
    """Everything after the model. No randomness, so a
    replay of saved outputs takes the same path."""
    ev = evidence_ok(inv["text"], r1.get("evidence", []))
    label = r1["label"]
    args = (inv["payee"], inv["amount"],
            inv["ytd_before"], d(inv["credit"]),
            d(inv["payment"]), inv.get("ytd_taxed", 0))
    dec = (None if label == "unclear"
           else rules.compute(label, *args))
    alts = (r1.get("alternatives", [])
            + r2.get("alternatives", []))
    exp = (0 if label == "unclear"
           else rules.exposure(label, alts, *args))
    hist = history_for(inv["vendor"], history)
    rt = route(r1, r2, ev, dec, exp, hist)
    return {"evidence_ok": ev, "decision": dec,
            "exposure": exp, "history": hist,
            "routing": rt}


def main():
    baseline_only = "--baseline" in sys.argv
    replay = "--replay" in sys.argv
    resume = "--resume" in sys.argv
    invoices = json.load(open("invoices.json"))
    history = json.load(open("vendor_history.json"))
    saved = {}
    if replay or resume:
        for line in open("audit_log.jsonl"):
            rec = json.loads(line)
            saved[rec["invoice"]["id"]] = rec
    rows = []
    log = None if baseline_only \
        else open("audit_log.jsonl", "w")

    for inv in invoices:
        base = keyword_baseline(inv["text"])
        row = {"id": inv["id"], "expected": inv["expected"],
               "contested": inv["contested"],
               "baseline": base}
        if not baseline_only:
            if replay or inv["id"] in saved:
                r1 = saved[inv["id"]]["run1"]
                r2 = saved[inv["id"]]["run2"]
                ts = saved[inv["id"]]["ts"]
            else:
                ts = datetime.now().isoformat()
                r1 = llm_classify(inv["text"], 0.3)
                time.sleep(4)      # free-tier rate limit
                r2 = llm_classify(inv["text"], 0.9)
                time.sleep(4)
            out = decide(inv, r1, r2, history)
            dec, rt = out["decision"], out["routing"]
            row.update({"llm": r1["label"],
                        "run2": r2["label"],
                        "tds": dec["tds"] if dec else "-",
                        "section": (dec["section"]
                                    if dec else "-"),
                        "act": dec["act"] if dec else "-",
                        "exposure": out["exposure"],
                        "coverage": evidence_coverage(
                            inv["text"],
                            r1.get("evidence", [])),
                        **rt})
            log.write(json.dumps({
                "ts": ts, "invoice": inv,
                "run1": r1, "run2": r2, **out,
                "rules_version": rules.RULES_VERSION,
            }) + "\n")
            log.flush()
        rows.append(row)
        print(row["id"], row.get("llm", ""), base)

    write_report(rows, baseline_only)


def trigger_counts(rows):
    """Invoices hit by each kind of review reason."""
    counts = {}
    for r in rows:
        kinds = {re.split(r"[:(]| Rs", reason)[0].strip()
                 for reason in r["reasons"]}
        for kind in kinds:
            counts[kind] = counts.get(kind, 0) + 1
    return dict(sorted(counts.items()))


def write_report(rows, baseline_only):
    n = len(rows)
    b_ok = sum(r["baseline"] == r["expected"] for r in rows)
    out = [f"# Results ({n} synthetic invoices)\n",
           f"Keyword baseline correct: {b_ok}/{n}\n"]
    if not baseline_only:
        l_ok = sum(r["llm"] == r["expected"] for r in rows)
        cont = [r for r in rows if r["contested"]]
        caught = sum(not r["would_auto_post"]
                     for r in cont)
        wrong_auto = [r["id"] for r in rows
                      if r["would_auto_post"]
                      and r["llm"] != r["expected"]]
        reviewed = sum(not r["would_auto_post"]
                       for r in rows)
        plain = [r for r in rows if not r["contested"]]
        plain_flagged = sum(not r["would_auto_post"]
                            for r in plain)
        median_cov = statistics.median(
            r["coverage"] for r in rows)
        out += [f"LLM label correct: {l_ok}/{n}\n",
                f"Contested cases flagged for review: "
                f"{caught}/{len(cont)}\n",
                f"Wrong AND would auto-post (worst "
                f"failure): {wrong_auto or 'none'}\n",
                f"Sent to review: {reviewed}/{n} "
                f"(so contested recall alone proves "
                f"little)\n",
                f"Non-contested sent to review: "
                f"{plain_flagged}/{len(plain)}\n",
                f"Invoices per review trigger: "
                f"{trigger_counts(rows)}\n",
                f"Median share of invoice quoted as "
                f"evidence: {median_cov:.0%}\n"]
    out.append("\n| id | expected | baseline | llm | "
               "act | section | tds | route reasons |")
    out.append("|---|---|---|---|---|---|---|---|")
    for r in rows:
        out.append(
            f"| {r['id']} | {r['expected']} | "
            f"{r['baseline']} | {r.get('llm', '-')} | "
            f"{r.get('act', '-')} | "
            f"{r.get('section', '-')} | "
            f"{r.get('tds', '-')} | "
            f"{'; '.join(r.get('reasons', [])) or '-'} |")
    open("results.md", "w").write("\n".join(out) + "\n")
    print("\n".join(out[:-(n + 2)]))


if __name__ == "__main__":
    main()
