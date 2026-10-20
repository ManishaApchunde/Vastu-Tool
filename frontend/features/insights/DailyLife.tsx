"use client";
import { useState } from "react";
import { PlanCanvas } from "@/components/PlanCanvas";
import { api } from "@/services/api";
import { InsightState, Panel, Pill, StaleNote, ToolIntro, useInsight } from "./shared";

const KIND = { blocks_door: "Blocks a door", blocks_window: "Blocks a window", tight_space: "Too tight",
  centre_furniture: "Furniture in the centre", ventilation: "Ventilation" };
const SEV_TONE = { high: "major", medium: "warning", low: "neutral" } as const;
const FILL = { high: "rgba(168,50,47,0.30)", medium: "rgba(176,115,26,0.26)", low: "rgba(90,107,123,0.16)" };

export function DailyLife({ projectId }: { projectId: string }) {
  const { data, error, noAnalysis, reload } = useInsight(
    () => Promise.all([api.conflicts(projectId), api.analysis(projectId)]), [projectId]);
  const [sel, setSel] = useState<string | null>(null);
  if (!data) return <InsightState projectId={projectId} error={error} noAnalysis={noAnalysis} reload={reload} />;
  const [d, a] = data;
  const worst = new Map<string, "high" | "medium" | "low">();
  const rank = { high: 0, medium: 1, low: 2 };
  d.conflicts.forEach((c) => { const w = worst.get(c.room_id); if (!w || rank[c.severity] < rank[w]) worst.set(c.room_id, c.severity); });
  const list = sel ? d.conflicts.filter((c) => c.room_id === sel) : d.conflicts;

  return (
    <div className="space-y-5">
      <ToolIntro slug="conflicts" />
      <StaleNote stale={d.stale} projectId={projectId} />
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
        <section className="panel p-4">
          <PlanCanvas imageUrl={a.image_url} width={a.image_width} height={a.image_height} zones={a.zones} centre={a.centre}
            northAngle={a.north_angle} openings={a.openings}
            rooms={a.rooms.map((r) => ({ id: r.id, label: r.label, polygon: r.polygon, fill: worst.has(r.id) ? FILL[worst.get(r.id)!] : undefined,
              highlighted: r.id === sel, stroke: r.id === sel ? "#16283A" : undefined }))}
            onRoomClick={(id) => setSel(id === sel ? null : id)} />
          <p className="mt-2 text-xs text-slate">Tinted rooms have a possible clash. Click a room to filter. Doors and windows are shown as marked on the Verify step.</p>
        </section>
        <div className="space-y-4">
          <div className="panel grid grid-cols-3 gap-3 p-4 text-sm">
            <div><p className="text-xs text-slate">Possible clashes</p><p className="font-display text-3xl">{d.conflicts.length}</p></div>
            <div><p className="text-xs text-slate">Rooms checked</p><p className="font-display text-3xl">{d.checked_rooms}</p></div>
            <div><p className="text-xs text-slate">Clear</p><p className="font-display text-3xl text-positive">{d.clear.length}</p></div>
          </div>
          {!d.scale_known && <p className="rounded border border-hairline bg-white p-3 text-xs text-slate">Add the built-up area to the project to also check whether furniture fits.</p>}
          <Panel title={sel ? `Clashes in ${a.rooms.find((r) => r.id === sel)?.label}` : "Possible clashes"}
            aside={sel ? <button className="text-xs underline" onClick={() => setSel(null)}>Show all</button> : undefined}>
            {list.length ? (
              <ul className="divide-y divide-hairline text-sm">
                {list.map((c, i) => (
                  <li key={`${c.finding_id}-${c.kind}-${i}`} className="space-y-1 px-4 py-3">
                    <div className="flex flex-wrap items-center gap-2"><span className="font-medium">{c.room}</span>
                      <Pill tone={SEV_TONE[c.severity]}>{KIND[c.kind]}</Pill></div>
                    <p className="text-ink-soft">{c.message}</p>
                    <p className="text-xs"><span className="text-slate">Try: </span>{c.suggestion}</p>
                  </li>
                ))}
              </ul>
            ) : <p className="px-4 py-3 text-sm text-positive">No clashes found{sel ? " in this room" : ""}.</p>}
          </Panel>
        </div>
      </div>
      {d.disruptions.length > 0 && (
        <Panel title="If you choose a structural option">
          <ul className="divide-y divide-hairline text-sm">{d.disruptions.map((x) => <li key={x.finding_id} className="px-4 py-2.5 text-ink-soft">{x.message}</li>)}</ul>
        </Panel>
      )}
      {d.clear.length > 0 && (
        <Panel title="Remedies with no clash found">
          <ul className="divide-y divide-hairline text-sm">{d.clear.map((x) => <li key={x.finding_id} className="px-4 py-2.5"><span className="font-medium">{x.room}:</span> <span className="text-ink-soft">{x.remedy}</span></li>)}</ul>
        </Panel>
      )}
      <p className="text-xs text-slate">{d.note}</p>
    </div>
  );
}
