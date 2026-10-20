"use client";
import { useEffect, useState } from "react";
import { ErrorNote, Spinner } from "@/components/ui";
import { api } from "@/services/api";
import type { FitConstraints, FitOption } from "@/types/insights";
import { BucketDot, InsightState, Panel, Pill, StaleNote, ToolIntro, useInsight, VERDICT } from "./shared";

const DEFAULTS: FitConstraints = { ownership: "owner", budget: "low", allow_structural: false, allow_services: false,
  max_disruption: "low", renovation_planned: false, society_restrictions: false };

export function FitCheck({ projectId }: { projectId: string }) {
  const { data: d, error, noAnalysis, reload } = useInsight(() => api.fitcheck(projectId), [projectId]);
  const [c, setC] = useState<FitConstraints>(DEFAULTS);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<unknown>(null);
  const [filter, setFilter] = useState<"all" | "fits" | "conditional" | "out_of_scope">("all");
  useEffect(() => { if (d) setC(d.constraints); }, [d]);

  async function save(next: FitConstraints) {
    setC(next); setSaving(true); setSaveError(null);
    try { await api.saveInsightContext(projectId, { fit_constraints: next }); await reload(); }
    catch (e) { setSaveError(e); } finally { setSaving(false); }
  }
  if (!d) return <InsightState projectId={projectId} error={error} noAnalysis={noAnalysis} reload={reload} />;
  const set = <K extends keyof FitConstraints>(k: K, v: FitConstraints[K]) => save({ ...c, [k]: v });
  const items = d.items.filter((i) => filter === "all" || i.verdict === filter);

  return (
    <div className="space-y-5">
      <ToolIntro slug="fitcheck">{saving && <span className="flex items-center gap-2 text-sm text-slate"><Spinner /> Updating</span>}</ToolIntro>
      <StaleNote stale={d.stale} projectId={projectId} />
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[300px_minmax(0,1fr)]">
        <Panel title="Your situation" className="self-start">
          <div className="space-y-4 p-4 text-sm">
            <Choice label="The home is" value={c.ownership} onChange={(v) => set("ownership", v)}
              options={[["owner", "Owned"], ["tenant", "Rented"], ["buying", "Being bought"]]} />
            <Choice label="Budget for changes" value={c.budget} onChange={(v) => set("budget", v)}
              options={[["none", "None"], ["low", "Low"], ["medium", "Moderate"], ["high", "High"]]} />
            <Choice label="Disruption you can live with" value={c.max_disruption} onChange={(v) => set("max_disruption", v)}
              options={[["none", "None"], ["low", "A little"], ["high", "Building work"]]} />
            <fieldset className="space-y-2">
              <legend className="label">Allowed work</legend>
              <Toggle checked={c.allow_structural} onChange={(v) => set("allow_structural", v)} label="Walls, floors or openings (civil work)" />
              <Toggle checked={c.allow_services} onChange={(v) => set("allow_services", v)} label="Plumbing or electrical changes" />
              <Toggle checked={c.renovation_planned} onChange={(v) => set("renovation_planned", v)} label="A renovation is already planned" />
              <Toggle checked={c.society_restrictions} onChange={(v) => set("society_restrictions", v)} label="Housing-society rules limit changes" />
            </fieldset>
            <p className="text-xs text-slate">Saved to this project. The construction stage (set in the Stage Assistant) also lowers the cost of early structural work.</p>
            <ErrorNote error={saveError} />
          </div>
        </Panel>

        <div className="space-y-4">
          <div className="panel p-4">
            <p className="font-medium">{d.headline}</p>
            <div className="mt-3 flex flex-wrap gap-1.5 text-sm">
              {(["all", "fits", "conditional", "out_of_scope"] as const).map((k) => (
                <button key={k} onClick={() => setFilter(k)} aria-pressed={filter === k}
                  className={`rounded border px-2.5 py-1 ${filter === k ? "border-ink bg-ink text-white" : "border-hairline bg-white text-ink-soft hover:border-slate"}`}>
                  {k === "all" ? `All ${d.items.length}` : `${VERDICT[k].label} ${d.counts[k]}`}
                </button>
              ))}
            </div>
          </div>
          {items.length === 0 && <p className="panel p-4 text-sm text-slate">Nothing in this group.</p>}
          {items.map((i) => (
            <article key={i.finding_id} className="panel">
              <header className="flex gap-3 border-b border-hairline px-4 py-3">
                <BucketDot bucket={i.bucket} />
                <div className="min-w-0 flex-1">
                  <p className="font-medium">{i.subject}</p>
                  <p className="text-sm text-ink-soft">{i.finding}</p>
                </div>
                <Pill tone={VERDICT[i.verdict].tone} className="self-start">{VERDICT[i.verdict].label}</Pill>
              </header>
              <div className="grid divide-y divide-hairline md:grid-cols-2 md:divide-x md:divide-y-0">
                {i.options.map((o) => <Option key={o.kind} o={o} recommended={i.recommended === o.kind} />)}
                {i.options.length === 1 && <p className="hidden p-4 text-sm text-slate md:block">The catalogue has no structural option for this issue.</p>}
              </div>
              {!i.approved && <p className="border-t border-hairline px-4 py-2 text-xs text-warning">No approved remedy in the catalogue yet; the only step is an expert opinion.</p>}
            </article>
          ))}
        </div>
      </div>
    </div>
  );
}

function Option({ o, recommended }: { o: FitOption; recommended: boolean }) {
  return (
    <div className={`space-y-2 p-4 text-sm ${o.verdict === "out_of_scope" ? "opacity-70" : ""}`}>
      <div className="flex flex-wrap items-center gap-2">
        <p className="font-medium">{o.title}</p>
        <Pill tone={VERDICT[o.verdict].tone}>{VERDICT[o.verdict].label}</Pill>
        {recommended && <Pill tone="ink">Suggested for you</Pill>}
      </div>
      <p className="text-ink-soft">{o.text}</p>
      <p className="text-xs text-slate">{o.cost_label} · disruption: {o.disruption}{o.requires_text.length ? ` · needs ${o.requires_text.join(", ")}` : ""}</p>
      <p className="text-xs text-ink-soft">{o.effect}</p>
      {[...o.blocked_by.map((t) => ["text-major", "✕", t]), ...o.conditions.map((t) => ["text-warning", "!", t]), ...o.notes.map((t) => ["text-slate", "i", t])]
        .map(([tone, mark, t]) => <p key={t} className="flex gap-2 text-xs"><span aria-hidden className={`w-3 text-center ${tone}`}>{mark}</span>{t}</p>)}
    </div>
  );
}

function Choice<T extends string>({ label, value, options, onChange }: { label: string; value: T; options: [T, string][]; onChange: (v: T) => void }) {
  return (
    <fieldset>
      <legend className="label">{label}</legend>
      <div className="flex flex-wrap gap-1">
        {options.map(([v, l]) => (
          <button key={v} type="button" aria-pressed={value === v} onClick={() => onChange(v)}
            className={`rounded border px-2.5 py-1 text-sm ${value === v ? "border-ink bg-ink text-white" : "border-hairline bg-white hover:border-slate"}`}>{l}</button>
        ))}
      </div>
    </fieldset>
  );
}

export function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <label className="flex items-start gap-2 text-sm text-ink-soft">
      <input type="checkbox" className="mt-0.5" checked={checked} onChange={(e) => onChange(e.target.checked)} />{label}
    </label>
  );
}
