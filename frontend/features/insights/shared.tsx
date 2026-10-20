"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { BUCKET_STYLE, ErrorNote, Loading } from "@/components/ui";
import { ApiError } from "@/services/api";
import type { Bucket } from "@/types/api";

export type ToolSlug =
  | "explain" | "passport" | "history" | "fitcheck" | "conflicts" | "family" | "stage" | "post-move" | "expert-review" | "voice";

export const TOOL_GROUPS: { title: string; tools: { slug: ToolSlug; label: string; mr: string; blurb: string }[] }[] = [
  {
    title: "Understand the result",
    tools: [
      { slug: "explain", label: "Explain the Score", mr: "स्कोअर समजावून सांगणे",
        blurb: "How the score was built, rule by rule, and what moves it most." },
      { slug: "passport", label: "Trust & Accuracy Passport", mr: "विश्वासार्हता व अचूकता",
        blurb: "Where North came from, what the AI drew, what you corrected, and how sure the result is." },
      { slug: "history", label: "Change History", mr: "बदलांचा इतिहास",
        blurb: "Compare scores and findings across versions of the plan." },
    ],
  },
  {
    title: "Plan your changes",
    tools: [
      { slug: "fitcheck", label: "Vastu FitCheck", mr: "व्यवहार्य उपाय",
        blurb: "Which remedies fit your budget, ownership and how much you can change." },
      { slug: "conflicts", label: "Daily-Life Conflicts", mr: "दैनंदिन वापरातील अडचणी",
        blurb: "Remedies that would block a door, a window or the way through a room." },
      { slug: "family", label: "Family Priority Mode", mr: "कुटुंबाच्या गरजांनुसार",
        blurb: "Put the rooms that matter most to your family first." },
      { slug: "stage", label: "Construction Stage Assistant", mr: "बांधकामाच्या टप्प्यानुसार",
        blurb: "What to do now, before it gets expensive, at your building stage." },
    ],
  },
  {
    title: "Check and share",
    tools: [
      { slug: "post-move", label: "Post-Move Verification", mr: "प्रत्यक्ष घराची पडताळणी",
        blurb: "Check the real house against the plan and track remedies." },
      { slug: "expert-review", label: "Expert Review Handoff", mr: "तज्ज्ञ तपासणी",
        blurb: "Send a review pack to your Vastu consultant or architect." },
      { slug: "voice", label: "Voice Report Explainer", mr: "ऑडिओ सारांश",
        blurb: "Listen to a short summary in मराठी or English." },
    ],
  },
];
export const ALL_TOOLS = TOOL_GROUPS.flatMap((g) => g.tools);

/** Loads one insight endpoint. `null` data with `noAnalysis` means the project hasn't been analysed. */
export function useInsight<T>(load: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [noAnalysis, setNoAnalysis] = useState(false);
  const reload = useCallback(async () => {
    try {
      setData(await load()); setError(null); setNoAnalysis(false);
    } catch (e) {
      if (e instanceof ApiError && e.code === "no_analysis") setNoAnalysis(true);
      else setError(e);
    }
  }, deps); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { reload(); }, [reload]);
  return { data, error, noAnalysis, reload, setData };
}

export function InsightState({ projectId, error, noAnalysis, reload, label }: {
  projectId: string; error: unknown; noAnalysis: boolean; reload: () => void; label?: string;
}) {
  if (noAnalysis) return (
    <div className="panel p-6 text-sm">
      <p className="font-medium">Run the analysis first</p>
      <p className="mt-1 text-ink-soft">These tools read the finished, verified analysis.</p>
      <Link className="btn-primary mt-4" href={`/projects/${projectId}/analysis`}>Go to analysis</Link>
    </div>
  );
  if (error) return <ErrorNote error={error} onRetry={reload} />;
  return <Loading label={label} />;
}

export function StaleNote({ stale, projectId }: { stale: boolean; projectId: string }) {
  if (!stale) return null;
  return (
    <div className="rounded border border-warning/30 bg-warning-light p-3 text-sm">
      The plan or North changed after the latest analysis, so this reflects the older result.{" "}
      <Link className="text-ink underline" href={`/projects/${projectId}/analysis`}>Re-run the analysis</Link> to update it.
    </div>
  );
}

export function ToolIntro({ slug, children }: { slug: ToolSlug; children?: React.ReactNode }) {
  const t = ALL_TOOLS.find((x) => x.slug === slug)!;
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h2 className="font-display text-2xl leading-tight text-ink">{t.label}</h2>
        <p className="text-sm text-slate"><span lang="mr">{t.mr}</span> · {t.blurb}</p>
      </div>
      {children && <div className="flex flex-wrap gap-2">{children}</div>}
    </div>
  );
}

const TONES = {
  positive: "bg-positive-light text-positive border-positive/30",
  warning: "bg-warning-light text-warning border-warning/30",
  major: "bg-major-light text-major border-major/30",
  neutral: "bg-paper text-slate border-hairline",
  ink: "bg-ink text-white border-ink",
  brass: "bg-brass-light text-brass border-brass/30",
} as const;
export type Tone = keyof typeof TONES;

export function Pill({ tone = "neutral", children, className = "" }: { tone?: Tone; children: React.ReactNode; className?: string }) {
  return <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-sm border px-1.5 py-0.5 text-xs font-medium ${TONES[tone]} ${className}`}>{children}</span>;
}

export function BucketDot({ bucket }: { bucket: Bucket }) {
  return <span className={`mt-1.5 inline-block h-2 w-2 shrink-0 rounded-full ${BUCKET_STYLE[bucket].dot}`} aria-label={BUCKET_STYLE[bucket].label} />;
}

export function Panel({ title, aside, children, className = "" }: {
  title?: React.ReactNode; aside?: React.ReactNode; children: React.ReactNode; className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      {title && (
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-hairline px-4 py-3">
          <h3 className="font-medium">{title}</h3>{aside}
        </div>
      )}
      {children}
    </section>
  );
}

export function Stat({ label, value, tone, sub }: { label: string; value: React.ReactNode; tone?: string; sub?: React.ReactNode }) {
  return (
    <div>
      <p className="text-xs text-slate">{label}</p>
      <p className={`font-display text-3xl leading-tight ${tone ?? "text-ink"}`}>{value}</p>
      {sub && <p className="text-xs text-slate">{sub}</p>}
    </div>
  );
}

export const LEVEL_TONE: Record<"high" | "medium" | "low", Tone> = { high: "positive", medium: "warning", low: "major" };
export const VERDICT: Record<"fits" | "conditional" | "out_of_scope", { label: string; tone: Tone }> = {
  fits: { label: "Fits", tone: "positive" },
  conditional: { label: "Needs approval", tone: "warning" },
  out_of_scope: { label: "Outside your limits", tone: "neutral" },
};

export function fmtDate(s: string | null | undefined) {
  return s ? new Date(s).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "—";
}
