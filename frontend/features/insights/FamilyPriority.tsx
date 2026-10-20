"use client";
import { useState } from "react";
import { ErrorNote, Spinner, scoreTone } from "@/components/ui";
import { api } from "@/services/api";
import type { FamilyProfile, Priority } from "@/types/insights";
import { BucketDot, InsightState, Panel, Pill, StaleNote, Stat, ToolIntro, useInsight } from "./shared";

const PRI_TONE = { high: "ink", normal: "neutral", low: "neutral" } as const;

export function FamilyPriority({ projectId }: { projectId: string }) {
  const { data: d, error, noAnalysis, reload } = useInsight(() => api.family(projectId), [projectId]);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<unknown>(null);
  if (!d) return <InsightState projectId={projectId} error={error} noAnalysis={noAnalysis} reload={reload} />;
  const p = d.profile;

  async function save(next: FamilyProfile) {
    setSaving(true); setSaveError(null);
    try { await api.saveInsightContext(projectId, { family_profile: next }); await reload(); }
    catch (e) { setSaveError(e); } finally { setSaving(false); }
  }
  const toggle = (list: string[], v: string) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);
  const setRoom = (id: string, v: Priority | "") => {
    const rp = { ...p.room_priority };
    if (v) rp[id] = v; else delete rp[id];
    save({ ...p, room_priority: rp });
  };

  return (
    <div className="space-y-5">
      <ToolIntro slug="family">{saving && <span className="flex items-center gap-2 text-sm text-slate"><Spinner /> Updating</span>}</ToolIntro>
      <StaleNote stale={d.stale} projectId={projectId} />
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[320px_minmax(0,1fr)]">
        <div className="space-y-4 self-start">
          <Panel title="Who lives here">
            <div className="flex flex-wrap gap-1.5 p-4">
              {Object.entries(d.options.roles).map(([k, r]) => (
                <Chip key={k} on={p.members.includes(k)} onClick={() => save({ ...p, members: toggle(p.members, k) })} label={r.label} mr={r.label_mr} />
              ))}
            </div>
          </Panel>
          <Panel title="What matters most">
            <div className="flex flex-wrap gap-1.5 p-4">
              {Object.entries(d.options.focus).map(([k, r]) => (
                <Chip key={k} on={p.focus.includes(k)} onClick={() => save({ ...p, focus: toggle(p.focus, k) })} label={r.label} mr={r.label_mr} />
              ))}
            </div>
          </Panel>
          <ErrorNote error={saveError} />
        </div>

        <div className="space-y-4">
          <div className="panel grid gap-4 p-5 sm:grid-cols-3">
            <Stat label="Official score" value={d.official_score ?? "—"} tone={scoreTone(d.official_score)} sub="unchanged, used in the report" />
            <Stat label="Your family view" value={d.family_score ?? "—"} tone={scoreTone(d.family_score)} sub="priority rooms count double" />
            <p className="self-center text-xs text-slate">{d.note}</p>
          </div>

          <Panel title="Rooms by priority">
            <table className="w-full text-sm">
              <tbody className="divide-y divide-hairline">
                {d.rooms.map((r) => (
                  <tr key={r.id} className="align-top">
                    <td className="px-4 py-2.5"><span className="flex gap-2"><BucketDot bucket={r.worst_bucket} /><span><span className="font-medium">{r.label}</span>
                      <span className="block text-xs text-slate">{r.room_type_label}{r.because.length ? ` · for ${r.because.join(", ")}` : ""}</span></span></span></td>
                    <td className="px-2 py-2.5"><Pill tone={PRI_TONE[r.priority]}>{r.priority}{r.priority_source === "you" ? " · set by you" : ""}</Pill></td>
                    <td className="px-4 py-2.5 text-right">
                      <label className="sr-only" htmlFor={`pri-${r.id}`}>Priority for {r.label}</label>
                      <select id={`pri-${r.id}`} className="rounded border border-hairline bg-white px-2 py-1 text-xs" value={p.room_priority[r.id] ?? ""}
                        onChange={(e) => setRoom(r.id, e.target.value as Priority | "")}>
                        <option value="">Automatic</option><option value="high">High</option><option value="normal">Normal</option><option value="low">Low</option>
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>

          <Panel title="Do these first">
            {d.priority_actions.length ? (
              <ol className="divide-y divide-hairline text-sm">
                {d.priority_actions.map((f, i) => (
                  <li key={f.finding_id} className="grid grid-cols-[24px_1fr] gap-2 px-4 py-2.5">
                    <span className="text-slate">{i + 1}.</span>
                    <div><p><span className="font-medium">{f.subject}</span>{f.priority === "high" && <Pill tone="ink" className="ml-2">family priority</Pill>}</p>
                      <p className="text-ink-soft">{f.finding}</p>
                      {f.recommendation && <p className="text-xs text-slate">{f.recommendation}</p>}</div>
                  </li>
                ))}
              </ol>
            ) : <p className="px-4 py-3 text-sm text-positive">No issues to act on.</p>}
          </Panel>

          {d.member_notes.length > 0 && (
            <div className="grid gap-4 md:grid-cols-2">
              {d.member_notes.map((m) => (
                <Panel key={m.role} title={<>{m.label} <span lang="mr" className="text-sm font-normal text-slate">{m.label_mr}</span></>}>
                  <div className="space-y-2 p-4 text-sm">
                    <p className="text-ink-soft">{m.note}</p>
                    {m.issues.map((x) => <p key={x.finding_id} className="flex gap-2"><BucketDot bucket={x.bucket} />{x.finding}</p>)}
                    {m.positives.slice(0, 2).map((x) => <p key={x.finding} className="flex gap-2 text-ink-soft"><BucketDot bucket="positive" />{x.finding}</p>)}
                    {!m.issues.length && !m.positives.length && <p className="text-slate">No rooms for this need on the plan.</p>}
                  </div>
                </Panel>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Chip({ on, onClick, label, mr }: { on: boolean; onClick: () => void; label: string; mr: string }) {
  return (
    <button type="button" aria-pressed={on} onClick={onClick}
      className={`rounded border px-2.5 py-1 text-left text-sm ${on ? "border-ink bg-ink text-white" : "border-hairline bg-white hover:border-slate"}`}>
      {label} <span lang="mr" className={`block text-xs ${on ? "text-white/75" : "text-slate"}`}>{mr}</span>
    </button>
  );
}
