"use client";
import Link from "next/link";
import { scoreTone } from "@/components/ui";
import { api } from "@/services/api";
import type { InsightSummary } from "@/types/insights";
import { InsightState, LEVEL_TONE, Pill, StaleNote, TOOL_GROUPS, type Tone, type ToolSlug, useInsight } from "./shared";

function status(slug: ToolSlug, s: InsightSummary): { text: string; tone?: Tone } {
  switch (slug) {
    case "explain": return { text: `Score ${s.overall_score ?? "—"}`, tone: "neutral" };
    case "passport": return { text: `${s.trust_level} confidence`, tone: LEVEL_TONE[s.trust_level] };
    case "history": return { text: `${s.versions} version${s.versions === 1 ? "" : "s"}` };
    case "fitcheck": return { text: `${s.fit_counts.fits} fit · ${s.fit_counts.conditional} need approval`, tone: "neutral" };
    case "conflicts": return s.conflicts ? { text: `${s.conflicts} possible clash${s.conflicts === 1 ? "" : "es"}`, tone: "warning" } : { text: "No clashes", tone: "positive" };
    case "family": return s.family_set ? { text: `Family view ${s.family_score ?? "—"}`, tone: "ink" } : { text: "Not set up" };
    case "stage": return s.stage ? { text: `${s.stage}${s.act_now ? ` · ${s.act_now} to act on now` : ""}`, tone: s.act_now ? "major" : "neutral" } : { text: "Stage not set" };
    case "post-move": return s.site_checks ? { text: `${s.site_checks} site check${s.site_checks === 1 ? "" : "s"}`, tone: "positive" } : { text: "Not done" };
    case "expert-review": return s.expert_reviews ? { text: `${s.expert_reviews} link${s.expert_reviews === 1 ? "" : "s"}`, tone: "neutral" } : { text: "Not sent" };
    case "voice": return { text: "मराठी · English" };
  }
}

export function InsightsOverview({ projectId }: { projectId: string }) {
  const { data: s, error, noAnalysis, reload } = useInsight(() => api.insightSummary(projectId), [projectId]);
  if (!s) return <InsightState projectId={projectId} error={error} noAnalysis={noAnalysis} reload={reload} label="Preparing insights" />;
  return (
    <div className="space-y-6">
      <StaleNote stale={s.stale} projectId={projectId} />
      <div className="panel flex flex-wrap items-center gap-x-8 gap-y-3 p-5">
        <div><p className="text-xs text-slate">Official score</p><p className={`font-display text-4xl ${scoreTone(s.overall_score)}`}>{s.overall_score ?? "—"}</p></div>
        <div><p className="text-xs text-slate">Trust</p><Pill tone={LEVEL_TONE[s.trust_level]} className="mt-1 text-sm capitalize">{s.trust_level}</Pill></div>
        <div><p className="text-xs text-slate">Plan checks</p><p className="text-sm">{s.plan_checks.error} errors · {s.plan_checks.warning} warnings</p></div>
        <p className="max-w-md text-sm text-ink-soft">These tools read your verified analysis. None of them changes the official score or the PDF report.</p>
      </div>
      {TOOL_GROUPS.map((g) => (
        <section key={g.title}>
          <h2 className="mb-2 text-sm font-medium text-slate">{g.title}</h2>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {g.tools.map((t) => {
              const st = status(t.slug, s);
              return (
                <Link key={t.slug} href={`/projects/${projectId}/insights/${t.slug}`}
                  className="panel group flex flex-col gap-1.5 p-4 transition-colors hover:border-slate">
                  <span className="flex items-start justify-between gap-2"><span className="font-medium group-hover:underline">{t.label}</span>
                    <Pill tone={st.tone ?? "neutral"}>{st.text}</Pill></span>
                  <span lang="mr" className="text-sm text-slate">{t.mr}</span>
                  <span className="text-sm text-ink-soft">{t.blurb}</span>
                </Link>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}
