"use client";
import { useState } from "react";
import { ErrorNote, Spinner } from "@/components/ui";
import { api } from "@/services/api";
import type { StageCode, StageItem } from "@/types/insights";
import { BucketDot, InsightState, Panel, Pill, StaleNote, ToolIntro, useInsight } from "./shared";

const REQ = { arrange: "furniture", decor: "decor", habit: "habits", electrical: "electrical", plumbing: "plumbing",
  civil: "civil work", expert: "expert" } as Record<string, string>;

export function ConstructionStage({ projectId }: { projectId: string }) {
  const { data: d, error, noAnalysis, reload } = useInsight(() => api.stagePlan(projectId), [projectId]);
  const [saving, setSaving] = useState<StageCode | null>(null);
  const [saveError, setSaveError] = useState<unknown>(null);
  if (!d) return <InsightState projectId={projectId} error={error} noAnalysis={noAnalysis} reload={reload} />;

  async function choose(code: StageCode) {
    setSaving(code); setSaveError(null);
    try { await api.saveInsightContext(projectId, { construction_stage: code }); await reload(); }
    catch (e) { setSaveError(e); } finally { setSaving(null); }
  }
  const idx = d.stages.findIndex((s) => s.code === d.stage);

  return (
    <div className="space-y-5">
      <ToolIntro slug="stage" />
      <StaleNote stale={d.stale} projectId={projectId} />
      <section className="panel p-4" aria-label="Construction stage">
        <p className="mb-3 text-sm font-medium">Where is the house today?</p>
        <ol className="grid gap-2 sm:grid-cols-3 lg:grid-cols-6">
          {d.stages.map((s, i) => {
            const current = s.code === d.stage, past = idx >= 0 && i < idx;
            return (
              <li key={s.code}>
                <button onClick={() => choose(s.code)} aria-pressed={current} disabled={!!saving}
                  className={`h-full w-full rounded border p-2.5 text-left text-sm transition-colors ${current ? "border-ink bg-ink text-white"
                    : past ? "border-hairline bg-paper text-slate" : "border-hairline bg-white hover:border-slate"}`}>
                  <span className="flex items-center gap-1.5 text-xs opacity-80">{i + 1} {saving === s.code && <Spinner className="h-3 w-3" />}</span>
                  <span className="block font-medium">{s.label}</span>
                  <span lang="mr" className="block text-xs opacity-75">{s.label_mr}</span>
                </button>
              </li>
            );
          })}
        </ol>
        {d.current && <p className="mt-3 text-sm text-ink-soft">{d.current.description}</p>}
        <ErrorNote error={saveError} />
      </section>

      {!d.stage ? <p className="text-sm text-slate">Choose a stage to see what to do now.</p> : (
        <>
          <div className="grid gap-4 lg:grid-cols-3">
            <List title="Act now" tone="major" items={d.act_now} empty="Nothing here is about to get more expensive."
              sub={d.next_stage ? `before ${d.next_stage.label}` : undefined} />
            <List title="Any time" tone="positive" items={d.anytime} empty="—" sub="stays cheap, even after you move in" />
            <List title="Costly at this stage" tone="neutral" items={d.costly_now} empty="Nothing." sub="means undoing finished work" />
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <Panel title={`Site checklist: ${d.current?.label}`}>
              {d.checklist.length ? (
                <ul className="space-y-2 p-4 text-sm">{d.checklist.map((t) => <li key={t} className="flex gap-2"><input type="checkbox" className="mt-1" aria-label={t} /><span>{t}</span></li>)}</ul>
              ) : <p className="p-4 text-sm text-slate">No stage-specific checks for this plan.</p>}
            </Panel>
            {d.next_stage && (
              <Panel title={`Moving on to ${d.next_stage.label}`}>
                <p className="p-4 text-sm text-ink-soft">
                  {d.becomes_costly_next.length
                    ? <>After this stage, these become expensive: <strong>{d.becomes_costly_next.map((r) => REQ[r] ?? r).join(", ")}</strong>. Settle anything that needs them first.</>
                    : "Nothing new becomes expensive at the next stage."}
                </p>
              </Panel>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function List({ title, tone, items, empty, sub }: { title: string; tone: "major" | "positive" | "neutral"; items: StageItem[]; empty: string; sub?: string }) {
  return (
    <Panel title={<span className="flex items-center gap-2">{title} <Pill tone={tone}>{items.length}</Pill></span>} aside={sub && <span className="text-xs text-slate">{sub}</span>}>
      {items.length ? (
        <ul className="divide-y divide-hairline text-sm">
          {items.map((i) => (
            <li key={`${i.finding_id}-${i.option}`} className="space-y-1 px-4 py-2.5">
              <p className="flex gap-2"><BucketDot bucket={i.bucket} /><span className="font-medium">{i.subject}</span>
                <span className="text-xs text-slate">{i.option === "structural" ? "structural" : "everyday"}</span></p>
              <p className="text-ink-soft">{i.text}</p>
              {i.why && <p className="text-xs text-slate">{i.why}</p>}
              {i.score_gain ? <p className="text-xs text-positive">Could raise the score by about {i.score_gain} points.</p> : null}
            </li>
          ))}
        </ul>
      ) : <p className="px-4 py-3 text-sm text-slate">{empty}</p>}
    </Panel>
  );
}
