export type Pt = [number, number];
export type Bucket = "positive" | "warning" | "major" | "info";
export type Source = "ai" | "ai_edited" | "user";

export type FloorPlanStatus =
  | "uploaded" | "processing" | "detected" | "detection_failed"
  | "verified" | "north_set" | "zoned" | "analyzed";

export interface Job {
  id: string;
  kind: "detection" | "report";
  status: "queued" | "running" | "succeeded" | "failed";
  attempts: number;
  max_attempts: number;
  error_code: string | null;
  error: string | null;
  can_retry: boolean;
}

export interface Room {
  id: string;
  label: string;
  room_type: string;
  polygon: Pt[];
  confidence: number | null;
  source: Source;
  primary_zone: string | null;
  direction: string | null;
}

export interface Opening {
  id: string;
  kind: "door" | "window";
  is_main_entrance: boolean;
  position: Pt;
  confidence: number | null;
  source: Source;
  zone: string | null;
  direction: string | null;
}

export interface Zone { code: string; name: string; polygon: Pt[]; coverage: number }

export interface FloorPlan {
  id: string;
  project_id: string;
  status: FloorPlanStatus;
  original_filename: string;
  content_type: string;
  width: number;
  height: number;
  quality: { blur_score: number; contrast: number; warnings: string[] } | null;
  image_url: string;
  detection_provider: string | null;
  has_detection: boolean;
  verified: boolean;
  boundary: Pt[] | null;
  centre: Pt | null;
  north: { north_angle: number; confirmed: boolean } | null;
  rooms: Room[];
  openings: Opening[];
  zones: Zone[];
  detection_job: Job | null;
}

export interface DetectedRoom { id: string; name: string; room_type: string; polygon: Pt[]; confidence: number }
export interface DetectedOpening { id: string; kind: "door" | "window"; position: Pt; is_main_entrance: boolean; confidence: number }
export interface Detection {
  provider: string;
  boundary: Pt[] | null;
  rooms: DetectedRoom[];
  doors: DetectedOpening[];
  windows: DetectedOpening[];
  stairs: { id: string; polygon: Pt[]; confidence: number }[];
  warnings: string[];
}

export interface Property {
  name: string | null;
  client_name: string | null;
  address: string | null;
  property_type: string;
  built_up_area_sqft: number | null;
  notes: string | null;
}

export interface Project {
  id: string;
  name: string;
  description: string | null;
  is_demo: boolean;
  created_at: string;
  updated_at: string;
  property: Property | null;
  floor_plan_id: string | null;
  floor_plan_status: FloorPlanStatus | null;
  overall_score: number | null;
  analysis_id: string | null;
  floor_plan?: FloorPlan;
}

export interface Remedy {
  id: string | null;
  code: string | null;
  problem: string;
  explanation: string;
  recommendation: string;
  priority: "high" | "medium" | "low";
  visual_instruction: string | null;
  approved: boolean;
  subject?: string;
  zone?: string | null;
  severity?: string;
}

export interface Finding {
  id: string;
  rule_code: string | null;
  category: string;
  subject_type: string;
  subject_ref: string | null;
  subject_label: string;
  room_type: string | null;
  zone: string | null;
  zone_name: string | null;
  direction: string | null;
  status: "preferred" | "acceptable" | "issue" | "not_evaluated";
  severity: string;
  bucket: Bucket;
  weight: number;
  earned: number;
  finding: string;
  explanation: string | null;
  remedy: Remedy | null;
}

export interface AnalysisRoom {
  id: string;
  label: string;
  room_type: string;
  room_type_label: string;
  polygon: Pt[];
  zone: string | null;
  zone_name: string | null;
  direction: string | null;
  rule_result: Finding["status"];
  worst_bucket: Bucket;
  finding: string | null;
  remedy: Remedy | null;
}

export interface CategoryBreakdown {
  category: string;
  label: string;
  earned: number;
  possible: number;
  findings: number;
  category_weight: number;
  score: number | null;
}

export interface Analysis {
  id: string;
  project_id: string;
  floor_plan_id: string;
  created_at: string;
  overall_score: number | null;
  category_scores: Record<string, number | null>;
  score_breakdown: {
    categories: CategoryBreakdown[];
    method: string;
    config: { status_points: Record<string, number>; issue_points: Record<string, number> };
  };
  counts: Record<Bucket, number>;
  north_angle: number;
  rule_set: { code: string; name: string; methodology: string; version: string; disclaimer: string };
  centre: Pt | null;
  boundary: Pt[] | null;
  zones: Zone[];
  openings: { id: string; kind: string; is_main_entrance: boolean; position: Pt; zone: string | null }[];
  image_url: string;
  image_width: number;
  image_height: number;
  rooms: AnalysisRoom[];
  findings: Finding[];
  remedies: Remedy[];
  summary: Finding[];
}

/** Language of a generated PDF report. */
export type ReportLanguage = "en" | "mr";

export interface Report {
  id: string;
  project_id: string;
  analysis_id: string;
  language: ReportLanguage;
  action_plan: boolean;
  status: "queued" | "running" | "ready" | "failed";
  error: string | null;
  download_url: string | null;
  created_at: string;
  job: Job | null;
}

export interface ReportVideo {
  id: string;
  project_id: string;
  analysis_id: string;
  language: ReportLanguage;
  status: "queued" | "running" | "ready" | "failed";
  progress: number;
  narration: "edge" | "gtts" | "silent" | null;
  duration_seconds: number | null;
  scenes: number | null;
  error: string | null;
  is_current: boolean;
  created_at: string;
  video_url: string | null;
  download_url: string | null;
  subtitles_url: string | null;
  captions_url: string | null;
  poster_url: string | null;
  transcript: { title: string; start: number; text: string }[] | null;
  job: Job | null;
}

export interface User { id: string; email: string; full_name: string | null }
