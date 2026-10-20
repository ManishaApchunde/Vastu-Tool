"""Loads everything the insight tools need about one analysis, once. Shared by the Insights API,
the PDF's personal action plan and the video report. With language="mr" the analysis wording
(findings, remedies, labels) is the Marathi catalogue translation, exactly as in the Marathi PDF;
codes, numbers and buckets are unchanged, so every tool makes the same decisions in both languages."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.insights import common
from app.insights.daily_life import detect_conflicts
from app.insights.explain import explain_score
from app.insights.family import family_view
from app.insights.fitcheck import fitcheck
from app.insights.mistakes import check_plan
from app.insights.passport import build_passport
from app.insights.stage import stage_plan
from app.models import Analysis, FloorPlan, Project, RuleSet, SiteVerification, VastuRule
from app.services import pipeline
from app.services.serializers import analysis_out


class Ctx:
    """Everything the insight tools need about one analysis, loaded once per request."""

    def __init__(self, db: Session, project: Project, analysis: Analysis | None = None, language: str = "en"):
        self.db, self.project, self.language = db, project, language
        self.analysis = analysis or common.latest_analysis(project)
        self.fp = db.get(FloorPlan, self.analysis.floor_plan_id)
        self.a = analysis_out(db, self.analysis)
        if language != "en":
            from app.reports.i18n import texts_for

            self.a = texts_for(language).localise_analysis(self.a, self.rule_templates())
        self.cfg = common.scoring_cfg(self.analysis)
        self.prop = project.property
        self.stale = common.is_stale(project, self.analysis)
        self._rules = None

    @property
    def rule_ctx(self):
        if self._rules is None:
            self._rules = pipeline.load_rule_context(self.db)
        return self._rules

    def rule_set(self) -> RuleSet:
        return self.db.get(RuleSet, self.analysis.rule_set_id)

    def approved_rule_codes(self) -> list[str]:
        return list(self.db.scalars(select(VastuRule.code).where(
            VastuRule.rule_set_id == self.analysis.rule_set_id, VastuRule.status == "approved")))

    def rules_pending_review(self) -> bool:
        return bool(self.db.scalar(select(VastuRule.id).where(
            VastuRule.rule_set_id == self.analysis.rule_set_id, VastuRule.status == "approved",
            VastuRule.approved_by.like("%pending%")).limit(1)))

    def rule_templates(self) -> dict[str, str]:
        return {r.code: r.finding_template for r in self.db.scalars(
            select(VastuRule).where(VastuRule.rule_set_id == self.analysis.rule_set_id))}

    def latest_site(self) -> SiteVerification | None:
        rows = [s for s in self.project.site_verifications if s.analysis_id == self.analysis.id]
        return rows[-1] if rows else None

    # tools
    def explain(self):
        return explain_score(self.a, self.cfg, self.approved_rule_codes())

    def gains(self):
        return {d["finding_id"]: d["overall_gain"] for d in self.explain()["drags"]}

    def passport(self):
        _, rules, catalogue, _ = self.rule_ctx
        return build_passport(project=self.project, analysis=self.analysis, fp=self.fp, a=self.a, rules=rules,
                              catalogue=catalogue, cfg=self.cfg, rule_set=self.rule_set(), site=self.latest_site(),
                              stale=self.stale, rules_pending_review=self.rules_pending_review())

    def fit(self, gains=None):
        return fitcheck(self.a, self.prop.fit_constraints if self.prop else None,
                        self.prop.construction_stage if self.prop else None, gains if gains is not None else self.gains())

    def conflicts(self):
        return detect_conflicts(self.a, self.analysis.input_snapshot or {}, self.analysis.north_angle,
                                common.ft_per_px(self.fp, self.prop.built_up_area_sqft if self.prop else None))

    def family(self):
        return family_view(self.a, self.cfg, self.prop.family_profile if self.prop else None)

    def stage(self, gains=None):
        return stage_plan(self.a, self.prop.construction_stage if self.prop else None,
                          gains if gains is not None else self.gains(), language=self.language)

    def plan_checks(self):
        snap = self.analysis.input_snapshot or {}
        return check_plan(rooms=snap.get("rooms", []), openings=snap.get("openings", []),
                          boundary=snap.get("boundary"), width=self.fp.width, height=self.fp.height,
                          detection=self.fp.detection,
                          property_type=self.prop.property_type if self.prop else None,
                          north={"north_angle": self.analysis.north_angle,
                                 "confirmed": bool(self.fp.north and self.fp.north.confirmed)})
