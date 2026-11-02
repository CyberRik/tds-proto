"""Deterministic routing: auto-post vs CA review.

Every reason for review is recorded so the CA (and an
auditor) can see why a case was escalated.
"""

# Label pairs that practitioners and tribunals dispute.
CONTESTED = [
    {"contract_work", "technical_services"},
    {"contract_work", "professional_fees"},
    {"technical_services", "professional_fees"},
    {"contract_work", "rent_plant_machinery"},
]

EXPOSURE_LIMIT = 1_000      # rupees; a policy choice
SHADOW_MODE = True          # v1: nothing auto-posts


def route(run1, run2, ev_ok, decision, exp,
          history_label=None):
    reasons = []
    label = run1["label"]

    if label == "unclear":
        reasons.append("model abstained")
    if run1["label"] != run2["label"]:
        reasons.append(
            f"runs disagree: {run1['label']} vs "
            f"{run2['label']}")
    if not ev_ok:
        reasons.append("evidence not found in input")
    if run1.get("confidence") == "low":
        reasons.append("low confidence")
    # one run's passing mention is noise; both must list it.
    # Money risk is still caught below: exposure uses both.
    alts = set(run1.get("alternatives", []))
    alts &= set(run2.get("alternatives", []))
    for alt in sorted(alts):
        if {label, alt} in CONTESTED:
            reasons.append(f"contested: {label}/{alt}")
    if decision and not decision["section_verified"]:
        reasons.append("section reference unverified")
    if exp > EXPOSURE_LIMIT:
        reasons.append(f"exposure Rs {exp:,}")
    # history may only ADD a flag, never approve
    if history_label and history_label != label:
        reasons.append(
            f"differs from CA-approved history "
            f"({history_label})")

    would_auto = not reasons
    final = "ca_review" if (reasons or SHADOW_MODE) \
        else "auto_post"
    return {"route": final,
            "would_auto_post": would_auto,
            "reasons": reasons}
