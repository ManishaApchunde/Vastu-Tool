"""Vastu FitCheck (Vastu Feasibility Checker).

For every issue, sets the remedy's options (the everyday recommendation, and the structural option
when the catalogue has one) against the household's situation: ownership, budget, whether walls or
plumbing/electrical can be touched, how much disruption is acceptable, and the construction stage.
The output says which option fits, which needs permission, and which is out of scope, with reasons."""
from app.insights.common import LEVELS, load_data, remedy_fit

DEFAULT_CONSTRAINTS = {"ownership": "owner", "budget": "low", "allow_structural": False, "allow_services": False,
                       "max_disruption": "low", "renovation_planned": False, "society_restrictions": False}
SERVICES = {"plumbing", "electrical"}
DISRUPTION = ("none", "low", "high")
REQUIRES_LABEL = {"arrange": "rearranging furniture or items", "decor": "colours, lighting or curtains",
                  "habit": "everyday habits", "electrical": "electrical or gas-point work",
                  "plumbing": "plumbing work", "civil": "civil work on walls or floors",
                  "expert": "an on-site check by a practitioner"}
COST_LABEL = {"none": "No cost", "low": "Low cost", "medium": "Moderate cost", "high": "High cost"}


def _stage_discount(option: dict, stage: str | None) -> str:
    """Before walls and services are finished, structural and service work costs much less."""
    band = option["cost_band"]
    if not stage:
        return band
    cheap = set(load_data("stages")["stages"].get(stage, {}).get("cheap", []))
    heavy = set(option["requires"]) & ({"civil"} | SERVICES)
    if heavy and heavy <= cheap and band in ("high", "medium"):
        return LEVELS[LEVELS.index(band) - 1]
    return band


def assess_option(option: dict, c: dict, *, stage: str | None, remedy_code: str | None, structural: bool) -> dict:
    req = set(option["requires"])
    cost = _stage_discount(option, stage)
    blocked, conditions, notes, codes = [], [], [], {"blocked": [], "conditions": [], "notes": []}

    def flag(kind: str, code: str, text: str):
        {"blocked": blocked, "conditions": conditions, "notes": notes}[kind].append(text)
        codes[kind].append(code)

    if LEVELS.index(cost) > LEVELS.index(c["budget"]):
        flag("blocked", "over_budget", f"{COST_LABEL[cost]}; above your budget ({COST_LABEL[c['budget']].lower()}).")
    if "civil" in req and not c["allow_structural"]:
        if c["renovation_planned"]:
            flag("conditions", "civil_with_renovation", "Needs civil work; only possible during your planned renovation.")
        else:
            flag("blocked", "no_civil", "Needs civil work, which you've ruled out.")
    if req & SERVICES and not c["allow_services"]:
        if c["renovation_planned"]:
            flag("conditions", "services_with_renovation",
                 "Needs plumbing or electrical changes; plan them with the renovation.")
        else:
            flag("blocked", "no_services", "Needs plumbing or electrical changes, which you've ruled out.")
    if DISRUPTION.index(option["disruption"]) > DISRUPTION.index(c["max_disruption"]):
        flag("blocked", "too_disruptive", "More disruption to daily life than you're willing to accept.")
    if c["ownership"] == "tenant" and req & ({"civil"} | SERVICES):
        flag("conditions", "owner_permission", "You rent: needs the owner's written permission.")
    if c["society_restrictions"] and structural and (remedy_code or "").startswith("entrance"):
        flag("blocked", "society_rules", "Housing-society rules usually don't allow moving the main door.")
    if c["ownership"] == "buying" and structural:
        flag("notes", "buying", "You're still buying: factor this cost into the price, or ask the seller/builder.")
    if "expert" in req:
        flag("notes", "expert", "Confirm on site with a Vastu practitioner first.")
    verdict = "out_of_scope" if blocked else "conditional" if conditions else "fits"
    return {"verdict": verdict, "cost_band": cost, "cost_label": COST_LABEL[cost],
            "disruption": option["disruption"], "requires": sorted(req),
            "requires_text": [REQUIRES_LABEL[r] for r in sorted(req) if r in REQUIRES_LABEL],
            "blocked_by": blocked, "conditions": conditions, "notes": notes, "codes": codes}


def fitcheck(a: dict, constraints: dict | None, stage: str | None = None, gains: dict | None = None) -> dict:
    c = {**DEFAULT_CONSTRAINTS, **(constraints or {})}
    gains = gains or {}
    items = []
    for f in a["findings"]:
        r = f.get("remedy")
        if f["status"] != "issue" or not r:
            continue
        meta = remedy_fit(r)
        options = [{"kind": "everyday", "title": "Everyday adjustment", "text": r["recommendation"],
                    "effect": "Eases the issue. The room stays where it is, so the score doesn't change.",
                    **assess_option(meta["everyday"], c, stage=stage, remedy_code=r.get("code"), structural=False)}]
        if meta["structural"]:
            gain = gains.get(f["id"])
            options.append({"kind": "structural", "title": "Structural change", "text": r["structural_note"],
                            "effect": "Can resolve the placement itself" + (
                                f"; the score could rise by about {gain:g} points if the rule then passes." if gain
                                else "."),
                            **assess_option(meta["structural"], c, stage=stage, remedy_code=r.get("code"),
                                            structural=True)})
        rank = {"fits": 0, "conditional": 1, "out_of_scope": 2}
        # Prefer the option that resolves the issue when it fits; otherwise the most doable one.
        best = min(options, key=lambda o: (rank[o["verdict"]], o["kind"] != "structural"))
        items.append({
            "finding_id": f["id"], "subject": f["subject_label"], "finding": f["finding"], "bucket": f["bucket"],
            "severity": f["severity"], "priority": r.get("priority"), "remedy_code": r.get("code"),
            "approved": r.get("approved", True), "options": options,
            "recommended": best["kind"] if best["verdict"] != "out_of_scope" else None,
            "verdict": best["verdict"],
        })
    order = {"high": 0, "medium": 1, "low": 2}
    items.sort(key=lambda i: ({"fits": 0, "conditional": 1, "out_of_scope": 2}[i["verdict"]],
                              order.get(i["priority"], 3)))
    counts = {v: sum(1 for i in items if i["verdict"] == v) for v in ("fits", "conditional", "out_of_scope")}
    headline = ("Nothing needs fixing under this rule set." if not items else
                f"{counts['fits']} of {len(items)} issues have a remedy that fits your situation"
                + (f", {counts['conditional']} need permission or a planned renovation" if counts["conditional"] else "")
                + (f", and {counts['out_of_scope']} are outside your limits" if counts["out_of_scope"] else "") + ".")
    return {"constraints": c, "stage": stage, "items": items, "counts": counts, "headline": headline}
