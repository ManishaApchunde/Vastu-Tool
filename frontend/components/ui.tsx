"use client";
import Link from "next/link";
import type { Bucket, FloorPlanStatus } from "@/types/api";
import { ApiError } from "@/services/api";

const STATUS: Record<FloorPlanStatus, { label: string; tone: string }> = {
  uploaded: { label: "Uploaded", tone: "bg-paper text-slate border-hairline" },
  processing: { label: "AI processing", tone: "bg-brass-light text-brass border-brass/30" },
  detected: { label: "AI detected", tone: "bg-brass-light text-brass border-brass/30" },
  detection_failed: { label: "Needs attention", tone: "bg-major-light text-major border-major/30" },
  verified: { label: "User verified", tone: "bg-positive-light text-positive border-positive/30" },
  north_set: { label: "North set", tone: "bg-positive-light text-positive border-positive/30" },
  zoned: { label: "Zones ready", tone: "bg-positive-light text-positive border-positive/30" },
  analyzed: { label: "Analysis complete", tone: "bg-ink text-white border-ink" },
};

export function StatusBadge({ status }: { status: FloorPlanStatus | null | undefined }) {
  const s = status ? STATUS[status] : { label: "No plan yet", tone: "bg-paper text-slate border-hairline" };
  return <span className={`inline-flex items-center rounded-sm border px-2 py-0.5 text-xs font-medium ${s.tone}`}>{s.label}</span>;
}

export const BUCKET_STYLE: Record<Bucket, { label: string; text: string; bg: string; dot: string; fill: string }> = {
  major: { label: "Major issue", text: "text-major", bg: "bg-major-light", dot: "bg-major", fill: "rgba(168,50,47,0.32)" },
  warning: { label: "Warning", text: "text-warning", bg: "bg-warning-light", dot: "bg-warning", fill: "rgba(176,115,26,0.28)" },
  positive: { label: "Positive", text: "text-positive", bg: "bg-positive-light", dot: "bg-positive", fill: "rgba(47,115,85,0.18)" },
  info: { label: "Not scored", text: "text-slate", bg: "bg-paper", dot: "bg-slate", fill: "rgba(90,107,123,0.10)" },
};

export function Spinner({ className = "" }: { className?: string }) {
  return (
    <svg className={`h-4 w-4 animate-spin ${className}`} viewBox="0 0 24 24" aria-hidden>
      <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeOpacity=".2" strokeWidth="3" />
      <path d="M21 12a9 9 0 0 0-9-9" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

export function Loading({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 py-16 text-slate" role="status">
      <Spinner /> {label}
    </div>
  );
}

export function ErrorNote({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  if (!error) return null;
  const e = error instanceof ApiError ? error : null;
  const message = e?.message ?? (error instanceof Error ? error.message : "Something went wrong.");
  return (
    <div className="rounded border border-major/30 bg-major-light px-4 py-3 text-sm text-ink" role="alert">
      <p className="font-medium text-major">{message}</p>
      {e?.hint && <p className="mt-1 text-ink-soft">{e.hint}</p>}
      {e?.details?.length ? (
        <ul className="mt-1 list-disc pl-5 text-ink-soft">
          {e.details.map((d, i) => <li key={i}>{d.field ? `${d.field}: ` : ""}{d.message}</li>)}
        </ul>
      ) : null}
      {onRetry && <button className="btn-secondary mt-3" onClick={onRetry}>Try again</button>}
    </div>
  );
}

const STEPS = [
  { key: "upload", label: "Upload plan" },
  { key: "verify", label: "Verify plan" },
  { key: "north", label: "Set North" },
  { key: "analysis", label: "Analysis" },
  { key: "report", label: "Report" },
] as const;
type StepKey = (typeof STEPS)[number]["key"];

export function progressOf(status: FloorPlanStatus | null | undefined): number {
  if (!status) return 0;
  if (["uploaded", "processing", "detected", "detection_failed"].includes(status)) return 1;
  if (status === "verified") return 2;
  if (status === "north_set" || status === "zoned") return 3;
  return 4;
}

/** The workflow is a real sequence, so steps are numbered. A step is reachable once the one before it is done. */
export function ProjectStepper({ projectId, status, current }: {
  projectId: string; status: FloorPlanStatus | null | undefined; current: StepKey | "insights";
}) {
  const done = progressOf(status);
  return (
    <nav aria-label="Workflow" className="border-b border-hairline">
      <ol className="flex flex-wrap gap-x-7 gap-y-2 pb-3 text-sm">
        {STEPS.map((s, i) => {
          const reachable = i <= done;
          const isCurrent = s.key === current;
          const complete = i < done;
          const content = (
            <span className={`flex items-center gap-2 ${isCurrent ? "text-ink font-medium" : reachable ? "text-ink-soft" : "text-slate/60"}`}>
              <span className={`flex h-5 w-5 items-center justify-center rounded-full border text-[11px] ${
                complete ? "border-positive bg-positive text-white" : isCurrent ? "border-ink text-ink" : "border-hairline"}`}>
                {complete ? "✓" : i + 1}
              </span>
              {s.label}
            </span>
          );
          return (
            <li key={s.key} aria-current={isCurrent ? "step" : undefined}>
              {reachable ? <Link href={`/projects/${projectId}/${s.key}`} className="hover:underline">{content}</Link> : content}
            </li>
          );
        })}
        <li className="ml-auto">
          {done >= 4 ? (
            <Link href={`/projects/${projectId}/insights`} aria-current={current === "insights" ? "page" : undefined}
              className={`flex items-center gap-2 hover:underline ${current === "insights" ? "font-medium text-ink" : "text-ink-soft"}`}>
              <span aria-hidden>✦</span> Insights
            </Link>
          ) : <span className="flex items-center gap-2 text-slate/60"><span aria-hidden>✦</span> Insights</span>}
        </li>
      </ol>
    </nav>
  );
}

export function scoreTone(score: number | null | undefined) {
  if (score == null) return "text-slate";
  if (score >= 75) return "text-positive";
  if (score >= 50) return "text-warning";
  return "text-major";
}
