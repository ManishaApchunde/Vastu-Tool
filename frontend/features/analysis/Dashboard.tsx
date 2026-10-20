"use client";
import { useMemo, useState } from "react";
import { ALL_LAYERS, PlanCanvas, type PlanLayers } from "@/components/PlanCanvas";
import { BUCKET_STYLE, scoreTone } from "@/components/ui";
import type { Analysis, Bucket, Finding, Remedy } from "@/types/api";

const STATUS_LABEL: Record<Finding["status"], string> = {
  preferred: "Preferred", acceptable: "Acceptable", issue: "Issue", not_evaluated: "Not evaluated",
};

export function ScorePanel({ a }: { a: Analysis }) {
  const [showMethod, setShowMethod] = useState(false);
  const cats = a.score_breakdown?.categories ?? [];
  return (
    <section className="panel p-5" aria-labelledby="score-h">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 id="score-h" className="text-sm text-slate">Overall Vastu score</h2>
          <p className={`font-display text-6xl leading-none ${scoreTone(a.overall_score)}`}>
            {a.overall_score ?? "—"}<span className="text-xl text-slate"> / 100</span>
          </p>
        </div>
        <dl className="flex gap-5 text-sm">
          {(["positive", "warning", "major"] as Bucket[]).map((b) => (
            <div key={b}>
              <dt className="flex items-center gap-1.5 text-slate"><span className={`h-2 w-2 rounded-full ${BUCKET_STYLE[b].dot}`} />{BUCKET_STYLE[b].label}</dt>
              <dd className={`font-display text-2xl ${BUCKET_STYLE[b].text}`}>{a.counts?.[b] ?? 0}</dd>
            </div>
          ))}
        </dl>
      </div>
      <div className="mt-5 space-y-2.5">
        {cats.map((c) => (
          <div key={c.category} className="grid grid-cols-[88px_1fr_40px] items-center gap-3 text-sm">
            <span className="text-ink-soft">{c.label}</span>
            <div className="h-2 rounded-full bg-paper" title={`${c.earned.toFixed(1)} of ${c.possible.toFixed(1)} points from ${c.findings} findings`}>
              {c.score != null && <div className={`h-2 rounded-full ${c.score >= 75 ? "bg-positive" : c.score >= 50 ? "bg-warning" : "bg-major"}`}
                style={{ width: `${Math.max(2, c.score)}%` }} />}
            </div>
            <span className={`text-right font-medium ${scoreTone(c.score)}`}>{c.score == null ? "n/a" : Math.round(c.score)}</span>
          </div>
        ))}
      </div>
      <button className="btn-quiet mt-3 px-0 text-xs" onClick={() => setShowMethod(!showMethod)} aria-expanded={showMethod}>
        {showMethod ? "Hide" : "How is this calculated?"}
      </button>
      {showMethod && (
        <div className="mt-2 space-y-2 rounded bg-paper p-3 text-xs text-ink-soft">
          <p>{a.score_breakdown.method}</p>
          <table className="w-full">
            <thead><tr className="text-left text-slate"><th className="py-1 font-normal">Category</th><th className="font-normal">Weight</th><th className="font-normal">Points</th><th className="font-normal">Findings</th></tr></thead>
            <tbody>
              {cats.map((c) => (
                <tr key={c.category}><td className="py-0.5">{c.label}</td><td>{Math.round(c.category_weight * 100)}%</td>
                  <td>{c.earned.toFixed(1)} / {c.possible.toFixed(1)}</td><td>{c.findings}</td></tr>
              ))}
            </tbody>
          </table>
          <p>Categories with no scored findings are left out of the overall score rather than counted as zero.</p>
        </div>
      )}
    </section>
  );
}

export function PlanPanel({ a, selected, onSelect }: { a: Analysis; selected: string | null; onSelect: (id: string | null) => void }) {
  const [layers, setLayers] = useState<PlanLayers>(ALL_LAYERS);
  const [northUp, setNorthUp] = useState(false);
  const [highlightIssues, setHighlightIssues] = useState(true);
  const rooms = a.rooms.map((r) => ({
    id: r.id, label: r.label, polygon: r.polygon,
    sublabel: r.zone_name ?? undefined,
    fill: highlightIssues ? BUCKET_STYLE[r.worst_bucket].fill : undefined,
    highlighted: r.id === selected,
    stroke: r.id === selected ? "#16283A" : undefined,
  }));
  const toggle = (k: keyof PlanLayers) => setLayers({ ...layers, [k]: !layers[k] });

  return (
    <section className="panel p-4" aria-label="Floor plan with Vastu overlay">
      <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
        {([["zones", "Zone grid"], ["centre", "Centre"], ["labels", "Labels"], ["openings", "Doors & windows"]] as const).map(([k, l]) => (
          <label key={k} className="flex items-center gap-1.5 text-ink-soft">
            <input type="checkbox" checked={layers[k]} onChange={() => toggle(k)} /> {l}
          </label>
        ))}
        <label className="flex items-center gap-1.5 text-ink-soft">
          <input type="checkbox" checked={highlightIssues} onChange={(e) => setHighlightIssues(e.target.checked)} /> Highlight issues
        </label>
        <label className="ml-auto flex items-center gap-1.5 text-ink-soft">
          <input type="checkbox" checked={northUp} onChange={(e) => setNorthUp(e.target.checked)} /> North up
        </label>
      </div>
      <PlanCanvas imageUrl={a.image_url} width={a.image_width} height={a.image_height} rooms={rooms}
        openings={a.openings} zones={a.zones} centre={a.centre} northAngle={a.north_angle}
        layers={layers} northUp={northUp} onRoomClick={(id) => onSelect(id === selected ? null : id)} />
      <div className="mt-3 flex flex-wrap gap-4 text-xs text-slate">
        {(["major", "warning", "positive", "info"] as Bucket[]).map((b) => (
          <span key={b} className="flex items-center gap-1.5"><span className="inline-block h-3 w-3 border border-hairline" style={{ background: BUCKET_STYLE[b].fill }} />{BUCKET_STYLE[b].label}</span>
        ))}
        <span className="flex items-center gap-1.5"><span className="text-brass">⊕</span> Centre (Brahmasthan)</span>
        <span className="flex items-center gap-1.5"><span className="inline-block h-3 w-3 rounded-full bg-ink" /> Main entrance</span>
      </div>
    </section>
  );
}

export function FindingCard({ f }: { f: Finding }) {
  const [open, setOpen] = useState(false);
  const s = BUCKET_STYLE[f.bucket];
  return (
    <li className="px-4 py-3">
      <div className="flex gap-3">
        <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${s.dot}`} aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="text-ink">{f.finding}</p>
          <p className="mt-0.5 text-xs text-slate">
            {s.label}{f.severity && f.bucket !== "positive" && f.bucket !== "info" ? ` · ${f.severity} severity` : ""} · {f.category}
            {f.zone_name ? ` · ${f.zone_name}` : ""}{f.rule_code ? ` · rule ${f.rule_code}` : ""}
          </p>
          {(f.explanation || f.remedy) && (
            <button className="mt-1 text-xs text-ink underline" onClick={() => setOpen(!open)} aria-expanded={open}>
              {open ? "Less" : f.remedy ? "Why, and what to do" : "Why"}
            </button>
          )}
          {open && (
            <div className="mt-2 space-y-2 text-sm text-ink-soft">
              {f.explanation && <p>{f.explanation}</p>}
              {f.remedy && <RemedyBody r={f.remedy} />}
            </div>
          )}
        </div>
      </div>
    </li>
  );
}

function RemedyBody({ r }: { r: Remedy }) {
  return (
    <div className="rounded border border-hairline bg-paper/60 p-3">
      <p className="font-medium text-ink">{r.recommendation}</p>
      {r.explanation && <p className="mt-1">{r.explanation}</p>}
      {r.visual_instruction && <p className="mt-1 text-xs text-slate">On the plan: {r.visual_instruction}</p>}
      {!r.approved && <p className="mt-1 text-xs text-warning">No approved remedy in the catalogue for this rule yet.</p>}
    </div>
  );
}

export function FindingsPanel({ a }: { a: Analysis }) {
  const tabs: { key: Bucket; label: string }[] = [
    { key: "major", label: "Major issues" }, { key: "warning", label: "Warnings" },
    { key: "positive", label: "Positive" }, { key: "info", label: "Not scored" },
  ];
  const by = useMemo(() => {
    const m: Record<Bucket, Finding[]> = { major: [], warning: [], positive: [], info: [] };
    a.findings.forEach((f) => m[f.bucket].push(f));
    return m;
  }, [a]);
  const [tab, setTab] = useState<Bucket>(by.major.length ? "major" : by.warning.length ? "warning" : "positive");
  return (
    <section className="panel" aria-labelledby="findings-h">
      <div className="flex flex-wrap items-center gap-1 border-b border-hairline px-3 pt-3">
        <h2 id="findings-h" className="sr-only">Findings</h2>
        {tabs.map((t) => (
          <button key={t.key} role="tab" aria-selected={tab === t.key} onClick={() => setTab(t.key)}
            className={`-mb-px border-b-2 px-3 pb-2 text-sm ${tab === t.key ? `border-ink text-ink` : "border-transparent text-slate hover:text-ink"}`}>
            {t.label} <span className={tab === t.key ? BUCKET_STYLE[t.key].text : ""}>{by[t.key].length}</span>
          </button>
        ))}
      </div>
      {by[tab].length ? (
        <ul className="divide-y divide-hairline">{by[tab].map((f) => <FindingCard key={f.id} f={f} />)}</ul>
      ) : (
        <p className="p-4 text-sm text-slate">{tab === "info" ? "Every room matched a rule." : "Nothing in this group."}</p>
      )}
    </section>
  );
}

export function RoomTable({ a, selected, onSelect }: { a: Analysis; selected: string | null; onSelect: (id: string | null) => void }) {
  const [open, setOpen] = useState<string | null>(null);
  return (
    <section className="panel" aria-labelledby="rooms-h">
      <h2 id="rooms-h" className="border-b border-hairline px-4 py-3 font-medium">Room analysis</h2>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-sm">
          <thead className="text-left text-xs text-slate">
            <tr className="border-b border-hairline">
              <th className="px-4 py-2 font-normal">Room</th><th className="px-2 font-normal" title="Compass direction of the room centre, seen from the Brahmasthan">Direction from centre</th><th className="px-2 font-normal">Zone</th>
              <th className="px-2 font-normal">Rule result</th><th className="px-2 font-normal">Finding</th><th className="px-4 font-normal">Remedy</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-hairline">
            {a.rooms.map((r) => {
              const s = BUCKET_STYLE[r.worst_bucket];
              return (
                <tr key={r.id} onClick={() => onSelect(r.id === selected ? null : r.id)}
                  className={`cursor-pointer align-top ${r.id === selected ? "bg-paper" : "hover:bg-paper/50"}`}>
                  <td className="px-4 py-2.5"><span className="font-medium">{r.label}</span><span className="block text-xs text-slate">{r.room_type_label}</span></td>
                  <td className="px-2 py-2.5">{r.direction ?? "—"}</td>
                  <td className="px-2 py-2.5">{r.zone_name ?? "—"}</td>
                  <td className="px-2 py-2.5">
                    <span className={`inline-flex items-center gap-1.5 rounded-sm px-1.5 py-0.5 text-xs ${s.bg} ${s.text}`}>
                      <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} />{STATUS_LABEL[r.rule_result]}
                    </span>
                  </td>
                  <td className="px-2 py-2.5 text-ink-soft">{r.finding ?? "No rule for this room type."}</td>
                  <td className="px-4 py-2.5">
                    {r.remedy ? (
                      <>
                        <button className="text-left text-ink underline" onClick={(e) => { e.stopPropagation(); setOpen(open === r.id ? null : r.id); }}>
                          {r.remedy.recommendation.length > 60 && open !== r.id ? `${r.remedy.recommendation.slice(0, 60)}…` : r.remedy.recommendation}
                        </button>
                        {open === r.id && <div className="mt-2 text-ink-soft"><RemedyBody r={r.remedy} /></div>}
                      </>
                    ) : <span className="text-slate">—</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function RemediesPanel({ a }: { a: Analysis }) {
  if (!a.remedies.length) return (
    <section className="panel p-4 text-sm text-slate">No remedies needed: nothing was flagged as an issue.</section>
  );
  return (
    <section className="panel" aria-labelledby="rem-h">
      <h2 id="rem-h" className="border-b border-hairline px-4 py-3 font-medium">Remedies <span className="font-normal text-slate">from the approved catalogue, highest priority first</span></h2>
      <ol className="divide-y divide-hairline">
        {a.remedies.map((r, i) => (
          <li key={`${r.code}-${i}`} className="grid gap-1 px-4 py-3 sm:grid-cols-[120px_1fr]">
            <div className="text-xs">
              <span className={`rounded-sm px-1.5 py-0.5 ${r.priority === "high" ? "bg-major-light text-major" : r.priority === "medium" ? "bg-warning-light text-warning" : "bg-paper text-slate"}`}>
                {r.priority} priority
              </span>
              {r.subject && <p className="mt-1.5 text-slate">{r.subject}</p>}
            </div>
            <div className="text-sm">
              <p className="font-medium">{r.problem}</p>
              <p className="mt-0.5 text-ink-soft">{r.recommendation}</p>
              {r.visual_instruction && <p className="mt-1 text-xs text-slate">On the plan: {r.visual_instruction}</p>}
              {!r.approved && <p className="mt-1 text-xs text-warning">Placeholder: no approved remedy for this rule yet.</p>}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
