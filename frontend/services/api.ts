import type { Analysis, Detection, FloorPlan, Finding, Job, Project, Remedy, Report, ReportLanguage, ReportVideo, User } from "@/types/api";
import type {
  Comparison, Conflicts, Explain, ExpertReview, Family, FitCheck, InsightContext, InsightSummary, Passport, PlanChecks,
  ReviewPack, SiteData, SiteResult, StagePlan, Version, VoiceScript,
} from "@/types/insights";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "vastu.token";

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public hint?: string,
              public details?: { field: string; message: string }[]) {
    super(message);
  }
}

export const auth = {
  get token() {
    return typeof window === "undefined" ? null : window.localStorage.getItem(TOKEN_KEY);
  },
  set(token: string) {
    window.localStorage.setItem(TOKEN_KEY, token);
  },
  clear() {
    window.localStorage.removeItem(TOKEN_KEY);
  },
};

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (auth.token) headers.set("Authorization", `Bearer ${auth.token}`);
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "network", "Can't reach the server. Check your connection and try again.");
  }
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const e = body?.error ?? {};
    if (res.status === 401 && typeof window !== "undefined" && !path.startsWith("/auth/")) {
      auth.clear();
      window.location.href = "/login";
    }
    throw new ApiError(res.status, e.code ?? "error", e.message ?? `Request failed (${res.status}).`, e.hint, e.details);
  }
  return body as T;
}

const json = (body: unknown) => JSON.stringify(body);

/** Upload with progress events (fetch can't report upload progress). */
function uploadFile(path: string, file: File, onProgress?: (pct: number) => void): Promise<FloorPlan> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_URL}${path}`);
    if (auth.token) xhr.setRequestHeader("Authorization", `Bearer ${auth.token}`);
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress?.(Math.round((e.loaded / e.total) * 100));
    xhr.onload = () => {
      let body: any = null;
      try { body = JSON.parse(xhr.responseText); } catch { /* not JSON */ }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body);
      else {
        const e = body?.error ?? {};
        reject(new ApiError(xhr.status, e.code ?? "upload_failed", e.message ?? "Upload failed.", e.hint));
      }
    };
    xhr.onerror = () => reject(new ApiError(0, "network", "Upload interrupted. Check your connection and try again."));
    const fd = new FormData();
    fd.append("file", file);
    xhr.send(fd);
  });
}

export const api = {
  register: (email: string, password: string, full_name?: string) =>
    request<{ access_token: string; user: User }>("/auth/register", { method: "POST", body: json({ email, password, full_name }) }),
  login: (email: string, password: string) =>
    request<{ access_token: string; user: User }>("/auth/login", { method: "POST", body: json({ email, password }) }),
  me: () => request<User>("/auth/me"),

  projects: () => request<Project[]>("/projects"),
  project: (id: string) => request<Project>(`/projects/${id}`),
  createProject: (body: unknown) => request<Project>("/projects", { method: "POST", body: json(body) }),
  createDemo: () => request<Project>("/projects/demo", { method: "POST" }),
  deleteProject: (id: string) => request<void>(`/projects/${id}`, { method: "DELETE" }),
  uploadFloorPlan: (projectId: string, file: File, onProgress?: (p: number) => void) =>
    uploadFile(`/projects/${projectId}/floor-plan`, file, onProgress),

  roomTypes: () => request<{ value: string; label: string }[]>("/room-types"),
  floorPlan: (id: string) => request<FloorPlan>(`/floor-plans/${id}`),
  detection: (id: string) =>
    request<{ status: string; detection: Detection | null; job: Job | null; quality: FloorPlan["quality"] }>(
      `/floor-plans/${id}/detection`),
  analyze: (id: string) => request<Job>(`/floor-plans/${id}/analyze`, { method: "POST" }),
  verify: (id: string, body: unknown) => request<FloorPlan>(`/floor-plans/${id}/verification`, { method: "PUT", body: json(body) }),
  setNorth: (id: string, north_angle: number) =>
    request<FloorPlan>(`/floor-plans/${id}/north`, { method: "PUT", body: json({ north_angle }) }),
  calculateZones: (id: string) => request<FloorPlan>(`/floor-plans/${id}/calculate-zones`, { method: "POST" }),
  runAnalysis: (id: string) => request<Analysis>(`/floor-plans/${id}/run-analysis`, { method: "POST" }),

  analysis: (projectId: string) => request<Analysis>(`/projects/${projectId}/analysis`),
  findings: (projectId: string) => request<Finding[]>(`/projects/${projectId}/findings`),
  remedies: (projectId: string) => request<Remedy[]>(`/projects/${projectId}/remedies`),
  /** Queues a PDF report. Without a language the API keeps its original behaviour (English). */
  createReport: (projectId: string, language?: ReportLanguage, includeActionPlan = true) =>
    request<Report>(`/projects/${projectId}/report`,
      language ? { method: "POST", body: json({ language, include_action_plan: includeActionPlan }) } : { method: "POST" }),
  createVideo: (projectId: string, language: ReportLanguage) =>
    request<ReportVideo>(`/projects/${projectId}/video`, { method: "POST", body: json({ language }) }),
  videos: (projectId: string) => request<ReportVideo[]>(`/projects/${projectId}/videos`),
  video: (id: string) => request<ReportVideo>(`/videos/${id}`),
  reports: (projectId: string) => request<Report[]>(`/projects/${projectId}/reports`),
  report: (id: string) => request<Report>(`/reports/${id}`),
  retryJob: (id: string) => request<Job>(`/jobs/${id}/retry`, { method: "POST" }),

  // --- customer insight tools ---
  planChecks: (fpId: string) => request<PlanChecks>(`/floor-plans/${fpId}/checks`),
  draftChecks: (fpId: string, body: unknown) =>
    request<PlanChecks>(`/floor-plans/${fpId}/checks`, { method: "POST", body: json(body) }),
  insightContext: (pid: string) => request<InsightContext>(`/projects/${pid}/insights/context`),
  saveInsightContext: (pid: string, body: Partial<InsightContext>) =>
    request<InsightContext>(`/projects/${pid}/insights/context`, { method: "PUT", body: json(body) }),
  insightSummary: (pid: string) => request<InsightSummary>(`/projects/${pid}/insights/summary`),
  explain: (pid: string) => request<Explain>(`/projects/${pid}/insights/explain`),
  passport: (pid: string) => request<Passport>(`/projects/${pid}/insights/passport`),
  fitcheck: (pid: string) => request<FitCheck>(`/projects/${pid}/insights/fitcheck`),
  conflicts: (pid: string) => request<Conflicts>(`/projects/${pid}/insights/conflicts`),
  family: (pid: string) => request<Family>(`/projects/${pid}/insights/family`),
  stagePlan: (pid: string) => request<StagePlan>(`/projects/${pid}/insights/stage`),
  history: (pid: string) => request<{ versions: Version[] }>(`/projects/${pid}/insights/history`),
  compareVersions: (pid: string, oldId: string, newId: string) =>
    request<Comparison>(`/projects/${pid}/insights/history/compare?old=${oldId}&new=${newId}`),
  voice: (pid: string, language: "en" | "mr") => request<VoiceScript>(`/projects/${pid}/insights/voice?language=${language}`),
  siteVerifications: (pid: string) => request<SiteData>(`/projects/${pid}/site-verifications`),
  createSiteVerification: (pid: string, body: unknown) =>
    request<SiteResult>(`/projects/${pid}/site-verifications`, { method: "POST", body: json(body) }),
  applySiteVerification: (pid: string, svId: string, use_site_north: boolean) =>
    request<{ applied_rooms: number; used_site_north: boolean; analysis_id: string; overall_score: number | null }>(
      `/projects/${pid}/site-verifications/${svId}/apply`, { method: "POST", body: json({ use_site_north }) }),
  expertReviews: (pid: string) => request<ExpertReview[]>(`/projects/${pid}/expert-reviews`),
  createExpertReview: (pid: string, body: unknown) =>
    request<ExpertReview & { token: string }>(`/projects/${pid}/expert-reviews`, { method: "POST", body: json(body) }),
  revokeExpertReview: (pid: string, id: string) =>
    request<ExpertReview>(`/projects/${pid}/expert-reviews/${id}/revoke`, { method: "POST" }),
  publicReview: (token: string) => request<{ review: ExpertReview; pack: ReviewPack }>(`/expert-review/${encodeURIComponent(token)}`),
  submitReview: (token: string, body: unknown) =>
    request<{ status: string; submitted_at: string }>(`/expert-review/${encodeURIComponent(token)}/feedback`,
      { method: "POST", body: json(body) }),
};
