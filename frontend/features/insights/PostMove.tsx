"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ErrorNote, Spinner, scoreTone } from "@/components/ui";
import { api } from "@/services/api";
import type { Progress, SiteData, SiteResult } from "@/types/insights";
import { BucketDot, fmtDate, InsightState, Panel, Pill, StaleNote, ToolIntro, useInsight } from "./shared";

const PROGRESS: [Progress, string][] = [["not_started", "Not started"], ["partial", "Partly done"], ["done", "Done"], ["not_possible", "Not possible"]];
const VERDICT = { matches: { label: "House matches the plan", tone: "positive" }, differences: { label: "Some differences", tone: "warning" },
  re_run: { label: "Re-run recommended", tone: "major" } } as const;

export function PostMove({ projectId }: { projectId: string }) {
  const { data: d, error, noAnalysis, reload } = useInsight(() => api.siteVerifications(projectId), [projectId]);
  const [roomTypes, setRoomTypes] = useState<{ value: string; label: string }[]>([]);
  useEffect(() => { api.roomTypes().then(setRoomTypes).catch(() => undefined); }, []);
  if (!d) return <InsightState projectId={projectId} error={error} noAnalysis={noAnalysis} reload={reload} />;
  return (
    <div className="space-y-5">
      <ToolIntro slug="post-move" />
      <StaleNote stale={d.stale} projectId={projectId} />
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <SiteForm d={d} roomTypes={roomTypes} projectId={projectId} onSaved={reload} />
        <div className="space-y-4">
          {d.verifications.length === 0 ? (
            <p className="panel p-4 text-sm text-slate">No site checks yet. Walk through the house, fill in the form and save it; the result appears here.</p>
          ) : d.verifications.map((v, i) => <SiteCard key={v.id} v={v} latest={i === 0} projectId={projectId} onApplied={reload}
            current={v.analysis_id === d.analysis_id} />)}
        </div>
      </div>
    </div>
  );
}

function SiteForm({ d, roomTypes, projectId, onSaved }: { d: SiteData; roomTypes: { value: string; label: string }[]; projectId: string; onSaved: () => void }) {
  const prev = d.verifications.find((v) => v.analysis_id === d.analysis_id);
  const [compass, setCompass] = useState<string>(prev?.compass_north_angle != null ? String(prev.compass_north_angle) : "");
  const [entrance, setEntrance] = useState<"" | "yes" | "no">(prev?.entrance_confirmed == null ? "" : prev.entrance_confirmed ? "yes" : "no");
  const [rooms, setRooms] = useState(() => Object.fromEntries(d.plan_rooms.map((r) => {
    const it = prev?.items.find((x) => x.room_id === r.id);
    return [r.id, { actual: it?.actual_room_type ?? r.room_type, present: it?.present ?? true }];
  })));
  const [progress, setProgress] = useState<Record<string, Progress>>(() => Object.fromEntries(
    d.issues.map((i) => [i.finding_id, prev?.remedies.items.find((x) => x.finding_id === i.finding_id)?.state ?? "not_started"])));
  const [notes, setNotes] = useState(prev?.notes ?? "");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const [compassMsg, setCompassMsg] = useState<string | null>(null);

  async function readCompass() {
    setCompassMsg(null);
    const DOE = (window as any).DeviceOrientationEvent;
    if (!DOE) { setCompassMsg("This device has no compass sensor. Use a compass app and type the reading."); return; }
    try { if (typeof DOE.requestPermission === "function" && (await DOE.requestPermission()) !== "granted") { setCompassMsg("Compass permission was not given."); return; } }
    catch { /* older browsers: no permission step */ }
    const done = (heading: number) => {
      // The phone points at the side of the house that is at the top of the drawing, so that
      // direction's bearing is `heading`; North is then (360 - heading) clockwise from the top.
      setCompass(String(Math.round((360 - heading) % 360)));
      setCompassMsg(`Phone heading ${Math.round(heading)}°. Take readings away from steel, cars and appliances.`);
      window.removeEventListener("deviceorientationabsolute", handler as EventListener, true);
      window.removeEventListener("deviceorientation", handler as EventListener, true);
    };
    const handler = (e: DeviceOrientationEvent & { webkitCompassHeading?: number }) => {
      if (typeof e.webkitCompassHeading === "number") done(e.webkitCompassHeading);
      else if (e.absolute && e.alpha != null) done((360 - e.alpha) % 360);
    };
    window.addEventListener("deviceorientationabsolute", handler as EventListener, true);
    window.addEventListener("deviceorientation", handler as EventListener, true);
    setTimeout(() => setCompassMsg((m) => m ?? "No reading. Use a compass app and type the value."), 4000);
  }

  async function save() {
    setBusy(true); setErr(null);
    try {
      await api.createSiteVerification(projectId, {
        compass_north_angle: compass.trim() === "" ? null : ((Number(compass) % 360) + 360) % 360,
        entrance_confirmed: entrance === "" ? null : entrance === "yes",
        items: d.plan_rooms.map((r) => ({ room_id: r.id, actual_room_type: rooms[r.id].actual, present: rooms[r.id].present })),
        remedy_progress: progress, notes: notes || null,
      });
      onSaved();
    } catch (e) { setErr(e); } finally { setBusy(false); }
  }

  return (
    <Panel title="Record what you found on site">
      <div className="space-y-5 p-4 text-sm">
        <fieldset>
          <legend className="label">Compass reading</legend>
          <p className="mb-2 text-xs text-slate">Stand facing the side of the house that is at the top of the drawing. The plan uses North at {Math.round(d.north_angle)}°.</p>
          <div className="flex flex-wrap items-center gap-2">
            <input className="field w-28" inputMode="decimal" value={compass} onChange={(e) => setCompass(e.target.value)} placeholder="e.g. 12" aria-label="North, degrees clockwise from the top of the drawing" />
            <span className="text-slate">° North from drawing top</span>
            <button type="button" className="btn-secondary" onClick={readCompass}>Use phone compass</button>
          </div>
          {compassMsg && <p className="mt-1 text-xs text-slate">{compassMsg}</p>}
        </fieldset>
        <fieldset>
          <legend className="label">Is the main entrance the one marked on the plan?</legend>
          <div className="flex gap-1">{([["yes", "Yes"], ["no", "No"], ["", "Not sure"]] as const).map(([v, l]) => (
            <button key={v} type="button" aria-pressed={entrance === v} onClick={() => setEntrance(v)}
              className={`rounded border px-2.5 py-1 ${entrance === v ? "border-ink bg-ink text-white" : "border-hairline bg-white"}`}>{l}</button>))}</div>
        </fieldset>
        <fieldset>
          <legend className="label">How each room is actually used</legend>
          <div className="max-h-72 overflow-auto rounded border border-hairline">
            <table className="w-full">
              <tbody className="divide-y divide-hairline">
                {d.plan_rooms.map((r) => {
                  const st = rooms[r.id];
                  const changed = st.actual !== r.room_type;
                  return (
                    <tr key={r.id} className={changed ? "bg-warning-light/50" : ""}>
                      <td className="px-3 py-2">{r.label}</td>
                      <td className="px-2 py-2">
                        <select aria-label={`Actual use of ${r.label}`} className="rounded border border-hairline bg-white px-2 py-1 text-xs" value={st.actual}
                          onChange={(e) => setRooms({ ...rooms, [r.id]: { ...st, actual: e.target.value } })}>
                          {(roomTypes.length ? roomTypes : [{ value: r.room_type, label: r.room_type }]).map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                        </select>
                      </td>
                      <td className="px-3 py-2 text-right text-xs">
                        <label className="flex items-center justify-end gap-1"><input type="checkbox" checked={st.present}
                          onChange={(e) => setRooms({ ...rooms, [r.id]: { ...st, present: e.target.checked } })} /> exists</label>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </fieldset>
        {d.issues.length > 0 && (
          <fieldset>
            <legend className="label">Remedy progress</legend>
            <ul className="divide-y divide-hairline rounded border border-hairline">
              {d.issues.map((i) => (
                <li key={i.finding_id} className="flex flex-wrap items-start justify-between gap-2 px-3 py-2">
                  <span className="flex min-w-0 flex-1 gap-2"><BucketDot bucket={i.bucket} /><span><span className="font-medium">{i.subject}</span>
                    <span className="block text-xs text-slate">{i.recommendation}</span></span></span>
                  <select aria-label={`Progress for ${i.subject}`} className="rounded border border-hairline bg-white px-2 py-1 text-xs" value={progress[i.finding_id]}
                    onChange={(e) => setProgress({ ...progress, [i.finding_id]: e.target.value as Progress })}>
                    {PROGRESS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                  </select>
                </li>
              ))}
            </ul>
          </fieldset>
        )}
        <div>
          <label className="label" htmlFor="site-notes">Notes</label>
          <textarea id="site-notes" className="field min-h-[72px]" value={notes} maxLength={4000} onChange={(e) => setNotes(e.target.value)} />
        </div>
        <ErrorNote error={err} />
        <button className="btn-primary w-full" onClick={save} disabled={busy}>{busy && <Spinner />} Save site check</button>
      </div>
    </Panel>
  );
}

function SiteCard({ v, latest, current, projectId, onApplied }: { v: SiteResult; latest: boolean; current: boolean; projectId: string; onApplied: () => void }) {
  const [useNorth, setUseNorth] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const [done, setDone] = useState<string | null>(null);
  const vd = VERDICT[v.verdict];
  async function apply() {
    setBusy(true); setErr(null);
    try {
      const r = await api.applySiteVerification(projectId, v.id, useNorth);
      setDone(`Applied ${r.applied_rooms} room change${r.applied_rooms === 1 ? "" : "s"}${r.used_site_north ? " and the site North" : ""}. New score: ${r.overall_score ?? "—"}.`);
      onApplied();
    } catch (e) { setErr(e); } finally { setBusy(false); }
  }
  return (
    <Panel title={<span className="flex items-center gap-2">Site check <span className="text-xs font-normal text-slate">{fmtDate(v.created_at)}</span></span>}
      aside={<Pill tone={vd.tone}>{vd.label}</Pill>} className={latest ? "" : "opacity-80"}>
      <div className="space-y-3 p-4 text-sm">
        {v.actions.length > 0 && <ul className="space-y-1">{v.actions.map((a) => <li key={a} className="flex gap-2"><span className="text-warning" aria-hidden>!</span>{a}</li>)}</ul>}
        <div className="grid gap-3 sm:grid-cols-3">
          <div><p className="text-xs text-slate">North</p><p>{v.north ? <span className={v.north.agrees ? "text-positive" : "text-major"}>{v.north.difference_deg}° apart</span> : "Not measured"}</p></div>
          <div><p className="text-xs text-slate">Remedies done</p><p>{v.remedies.percent_done != null ? `${v.remedies.percent_done}%` : "—"} <span className="text-xs text-slate">({v.remedies.tally.done} done, {v.remedies.tally.partial} partly)</span></p></div>
          <div><p className="text-xs text-slate">Rooms used differently</p><p>{v.retyped_rooms.length}</p></div>
        </div>
        {v.retyped_rooms.length > 0 && <p className="text-ink-soft">{v.retyped_rooms.map((r) => `${r.room}: ${r.planned} → ${r.actual}`).join("; ")}</p>}
        {v.as_built && (
          <div className="rounded bg-paper p-3">
            <p className="text-xs text-slate">Simulated "as built" score{v.as_built.used_site_north ? " (with the site North)" : ""}</p>
            <p><span className={`font-display text-2xl ${scoreTone(v.as_built.overall_score)}`}>{v.as_built.overall_score ?? "—"}</span>
              <span className="text-slate"> vs {v.as_built.official_score} on the plan</span></p>
            {v.as_built.issues_in_changed_rooms.slice(0, 4).map((f) => <p key={f.finding} className="mt-1 flex gap-2 text-xs"><BucketDot bucket={f.bucket} />{f.finding}</p>)}
          </div>
        )}
        {v.applied_at ? <p className="text-xs text-positive">Applied {fmtDate(v.applied_at)}. See <Link className="underline" href={`/projects/${projectId}/insights/history`}>Change History</Link>.</p>
          : latest && current && (v.retyped_rooms.length > 0 || (v.north && !v.north.agrees)) && (
            <div className="space-y-2 border-t border-hairline pt-3">
              {v.north && !v.north.agrees && (
                <label className="flex items-center gap-2"><input type="checkbox" checked={useNorth} onChange={(e) => setUseNorth(e.target.checked)} /> Also use the site North ({Math.round(v.north.site)}°)</label>
              )}
              <button className="btn-secondary" onClick={apply} disabled={busy}>{busy && <Spinner />} Apply to the plan and re-run</button>
              <p className="text-xs text-slate">The current result stays in the change history.</p>
            </div>
          )}
        {done && <p className="text-xs text-positive">{done}</p>}
        <ErrorNote error={err} />
      </div>
    </Panel>
  );
}
