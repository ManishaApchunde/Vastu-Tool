import type { Bucket, Pt, Remedy, Zone } from "@/types/api";

export interface InsightMeta { analysis_id: string; stale: boolean }

export type Severity = "error" | "warning" | "info";
export interface PlanCheck {
  code: string; severity: Severity; title: string; message: string; hint: string;
  category: "rooms" | "openings" | "outline" | "north"; subject_ids: string[];
}
export interface PlanChecks { subject?: "verified" | "detection" | "draft"; checks: PlanCheck[]; counts: Record<Severity, number>; ok: boolean }

export interface InsightSummary extends InsightMeta {
  overall_score: number | null; trust_level: TrustLevel; trust_reasons: number;
  fit_counts: Record<FitVerdict, number>; conflicts: number; family_score: number | null; family_set: boolean;
  stage: string | null; act_now: number; versions: number; site_checks: number; expert_reviews: number;
  plan_checks: Record<Severity, number>;
}

// Explain the score
export interface ExplainItem {
  finding_id: string; subject: string; finding: string; status: string; severity: string; rule_code: string | null;
  weight: number; points: number; earned: number; lost: number; explanation: string | null;
}
export interface ExplainCategory {
  category: string; label: string; category_weight: number; score: number | null; earned: number; possible: number;
  share_of_overall: number | null; contribution?: number; items: ExplainItem[];
}
export interface ScoreDrag {
  finding_id: string; subject: string; finding: string; category: string; severity: string; bucket: Bucket;
  overall_gain: number; structural_only: boolean;
}
export interface Explain extends InsightMeta {
  overall: number | null; overall_exact: number | null; steps: string[];
  points: { status_points: Record<string, number>; issue_points: Record<string, number>; category_weights: Record<string, number> };
  categories: ExplainCategory[]; drags: ScoreDrag[]; ceiling_if_all_issues_resolved: number | null;
  not_scored: { subject: string; finding: string }[];
  rules: { approved_in_rule_set: number; triggered: number; triggered_codes: string[]; not_triggered: number };
  note: string;
}

// Trust passport
export type TrustLevel = "high" | "medium" | "low";
export interface Passport extends InsightMeta {
  level: TrustLevel;
  reasons: { severity: "critical" | "caution"; text: string }[];
  strengths: string[];
  north: { angle: number; confirmed: boolean; confirmed_at: string | null; is_image_top: boolean;
    site_check: { compass_angle: number; difference_deg: number; agrees: boolean; recorded_at: string } | null };
  detection: { provider: string | null; is_mock: boolean; detected_rooms: number; kept_unchanged: number; edited: number;
    added_by_user: number; removed: number; average_confidence: number | null; low_confidence_unreviewed: string[];
    quality_warnings: string[]; openings_by_source: Record<string, number> };
  uncertainty: {
    north_sensitivity: { degrees: number; score_now: number | null; score_min: number | null; score_max: number | null;
      rooms_changing_zone: { room_id: string; label: string; zone_now: string; could_be: string[] }[] } | null;
    borderline_rooms: { room_id: string; label: string; zone: string; zone_name: string; share: number; second_zone: string; second_share: number }[];
    not_scored_rooms: string[]; placeholder_remedies: string[];
  };
  rule_set: { name: string; version: string; methodology: string; pending_expert_review: boolean };
  plan_checks: Record<Severity, number>; plan_check_items: PlanCheck[];
  analysed_at: string;
}

// FitCheck
export type FitVerdict = "fits" | "conditional" | "out_of_scope";
export type Level = "none" | "low" | "medium" | "high";
export interface FitConstraints {
  ownership: "owner" | "tenant" | "buying"; budget: Level; allow_structural: boolean; allow_services: boolean;
  max_disruption: "none" | "low" | "high"; renovation_planned: boolean; society_restrictions: boolean;
}
export interface FitOption {
  kind: "everyday" | "structural"; title: string; text: string; effect: string; verdict: FitVerdict;
  cost_band: Level; cost_label: string; disruption: string; requires: string[]; requires_text: string[];
  blocked_by: string[]; conditions: string[]; notes: string[];
}
export interface FitItem {
  finding_id: string; subject: string; finding: string; bucket: Bucket; severity: string; priority: string;
  remedy_code: string | null; approved: boolean; options: FitOption[]; recommended: "everyday" | "structural" | null;
  verdict: FitVerdict;
}
export interface FitCheck extends InsightMeta {
  constraints: FitConstraints; stage: string | null; items: FitItem[]; counts: Record<FitVerdict, number>; headline: string;
}

// Daily life
export interface Conflict {
  finding_id: string; room_id: string; room: string; remedy_code: string | null;
  kind: "blocks_door" | "blocks_window" | "tight_space" | "centre_furniture" | "ventilation";
  severity: "high" | "medium" | "low"; message: string; suggestion: string;
}
export interface Conflicts extends InsightMeta {
  conflicts: Conflict[]; clear: { finding_id: string; room: string; remedy: string }[];
  disruptions: { finding_id: string; subject: string; message: string; requires: string[] }[];
  checked_rooms: number; scale_known: boolean; note: string;
}

// Family
export type Priority = "high" | "normal" | "low";
export interface FamilyProfile { members: string[]; focus: string[]; room_priority: Record<string, Priority> }
export interface Family extends InsightMeta {
  profile: FamilyProfile;
  options: { roles: Record<string, { label: string; label_mr: string }>; focus: Record<string, { label: string; label_mr: string }> };
  official_score: number | null; family_score: number | null;
  rooms: { id: string; label: string; room_type: string; room_type_label: string; priority: Priority;
    priority_source: "you" | "family" | "default"; because: string[]; worst_bucket: Bucket; finding: string | null }[];
  priority_actions: { finding_id: string; subject: string; finding: string; bucket: Bucket; priority: Priority; recommendation: string | null }[];
  member_notes: { role: string; label: string; label_mr: string; note: string;
    issues: { finding_id: string; subject: string; finding: string; bucket: Bucket }[];
    positives: { subject: string; finding: string }[] }[];
  note: string;
}

// Stage
export type StageCode = "planning" | "foundation" | "structure" | "services" | "finishing" | "occupied";
export interface StageItem {
  finding_id: string; subject: string; finding: string; bucket: Bucket; option: "everyday" | "structural";
  text: string; requires: string[]; score_gain: number | null; why?: string; deadline_stage?: string; deadline_label?: string;
}
export interface StagePlan extends InsightMeta {
  stage: StageCode | null;
  stages: { code: StageCode; label: string; label_mr: string; description: string }[];
  current?: { code: StageCode; label: string; label_mr: string; description: string };
  act_now: StageItem[]; anytime: StageItem[]; costly_now: StageItem[]; checklist: string[];
  next_stage: { code: StageCode; label: string } | null; becomes_costly_next: string[];
}

// History
export interface Version {
  id: string; version: number; created_at: string; overall_score: number | null; category_scores: Record<string, number | null>;
  counts: Record<Bucket, number>; north_angle: number; rooms: number; floor_plan_id: string; plan_file: string | null;
  is_latest: boolean; room_labels: string[];
}
export interface Comparison {
  old: { id: string; created_at: string; overall_score: number | null; north_angle: number };
  new: { id: string; created_at: string; overall_score: number | null; north_angle: number };
  score_delta: number | null; north_changed: boolean;
  categories: { category: string; old: number | null; new: number | null; delta: number | null }[];
  findings: {
    improved: { subject: string; old: string; new: string; old_bucket: Bucket; new_bucket: Bucket }[];
    worsened: { subject: string; old: string; new: string; old_bucket: Bucket; new_bucket: Bucket }[];
    resolved: { subject: string; finding: string; bucket: Bucket }[];
    new_issues: { subject: string; finding: string; bucket: Bucket }[];
    unchanged: number;
  };
  rooms: { added: string[]; removed: string[]; moved_zone: { room: string; old_zone: string; new_zone: string }[];
    retyped: { room: string; old_type: string; new_type: string }[] };
}

// Post-move
export type Progress = "done" | "partial" | "not_started" | "not_possible";
export interface SiteResult {
  id: string; analysis_id: string; created_at: string; applied_at: string | null;
  verdict: "matches" | "differences" | "re_run"; actions: string[];
  north: { plan: number; site: number; difference_deg: number; agrees: boolean } | null;
  entrance_confirmed: boolean | null;
  retyped_rooms: { room_id: string; room: string; planned: string; actual: string; note: string | null }[];
  missing_rooms: string[];
  as_built: { overall_score: number | null; official_score: number | null; delta: number | null; used_site_north: boolean;
    issues_in_changed_rooms: { subject: string; finding: string; bucket: Bucket }[] } | null;
  remedies: { items: { finding_id: string; subject: string; finding: string; recommendation: string; state: Progress }[];
    tally: Record<Progress, number>; percent_done: number | null };
  notes: string | null; compass_north_angle: number | null;
  items: { room_id: string; actual_room_type: string | null; present: boolean; note: string | null }[];
}
export interface SiteData extends InsightMeta {
  plan_rooms: { id: string; label: string; room_type: string }[];
  issues: { finding_id: string; subject: string; finding: string; recommendation: string; bucket: Bucket }[];
  north_angle: number; verifications: SiteResult[];
}

// Expert review
export interface ExpertReview {
  id: string; analysis_id: string; expert_name: string | null; expert_role: string | null; message: string | null;
  status: "open" | "submitted" | "revoked"; expires_at: string; created_at: string; submitted_at: string | null;
  reviewer_signature: string | null; include_contact: boolean;
  feedback: { verdict: "agree" | "agree_with_changes" | "disagree"; summary: string; north_confirmed: boolean | null;
    items: Record<string, { agree: boolean | null; comment: string | null }> } | null;
  token?: string;
}
export interface ReviewPack {
  project: { name: string; property_type: string | null; built_up_area_sqft: number | null; address: string | null; client_name: string | null };
  message: string | null;
  analysis: { id: string; created_at: string; overall_score: number | null; category_scores: Record<string, number | null>;
    counts: Record<Bucket, number>; north_angle: number; rule_set: { name: string; version: string; methodology: string; disclaimer: string } };
  plan: { image_url: string; image_width: number; image_height: number; zones: Zone[]; centre: Pt | null; boundary: Pt[] | null;
    openings: { id: string; kind: string; is_main_entrance: boolean; position: Pt; zone: string | null }[];
    rooms: { id: string; label: string; room_type: string; room_type_label: string; polygon: Pt[]; zone: string | null;
      zone_name: string | null; direction: string | null; worst_bucket: Bucket }[] };
  findings: { id: string; rule_code: string | null; category: string; subject_label: string; zone_name: string | null; status: string;
    severity: string; bucket: Bucket; finding: string; explanation: string | null; remedy: Remedy | null }[];
  passport: Pick<Passport, "level" | "reasons" | "strengths" | "north" | "detection" | "uncertainty">;
  plan_checks: PlanCheck[]; score_drags: ScoreDrag[];
  household: { constraints: FitConstraints; construction_stage: { label: string } | null; family: FamilyProfile | null };
  questions: string[]; conflicts: Conflict[];
}

// Voice
export interface VoiceScript extends InsightMeta {
  language: "en" | "mr"; voice_lang: string;
  segments: { id: string; title: string; text: string; speech: string }[];
  full_text: string; speech_text: string;
}

export interface InsightContext {
  fit_constraints: FitConstraints | null; family_profile: FamilyProfile | null; construction_stage: StageCode | null;
}
