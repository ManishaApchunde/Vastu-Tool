"use client";
import Link from "next/link";
import { api } from "@/services/api";
import type { PlanCheck } from "@/types/insights";
import { fmtDate, InsightState, LEVEL_TONE, Panel, Pill, StaleNote, Stat, ToolIntro, useInsight } from "./shared";

const LEVEL_TEXT = { high: "High confidence", medium: "Medium confidence", low: "Low confidence" };

export function TrustPassport({ projectId }: { projectId: string }) {
  const { data: d, error, noAnalysis, reload } = useInsight(() => api.passport(projectId), [projectId]);
  if (!d) return <InsightState projectId={projectId} error={error} noAnalysis={noAnalysis} reload={reload} />;
  const det = d.detection, sens = d.uncertainty.north_sensitivity;

  return (
    <div className="space-y-5">
      <ToolIntro slug="passport" />
      <StaleNote stale={d.stale} projectId={projectId} />

      <section className="panel overflow-hidden">
        <div className="grid gap-5 p-5 md:grid-cols-[220px_1fr]">
          <div className="border-hairline md:border-r md:pr-5">
            <p className="text-xs uppercase tracking-wide text-slate">Passport</p>
            <p className="mt-1 font-display text-3xl">{LEVEL_TEXT[d.level]}</p>
            <Pill tone={LEVEL_TONE[d.level]} className="mt-2">{d.reasons.length} point{d.reasons.length === 1 ? "" : "s"} to note</Pill>
            <p className="mt-3 text-xs text-slate">Analysed {fmtDate(d.analysed_at)}<br />Rule set {d.rule_set.name} v{d.rule_set.version}</p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <p className="text-sm font-medium">Lowers confidence</p>
              {d.reasons.length ? (
                <ul className="mt-1.5 space-y-1.5 text-sm">
                  {d.reasons.map((r) => (
                    <li key={r.text} className="flex gap-2"><span aria-hidden className={r.severity === "critical" ? "text-major" : "text-warning"}>!</span><span>{r.text}</span></li>
                  ))}
                </ul>
              ) : <p className="mt-1.5 text-sm text-slate">Nothing.</p>}
            </div>
            <div>
              <p className="text-sm font-medium">Supports it</p>
              <ul className="mt-1.5 space-y-1.5 text-sm text-ink-soft">
                {d.strengths.map((s) => <li key={s} className="flex gap-2"><span aria-hidden className="text-positive">✓</span><span>{s}</span></li>)}
              </ul>
            </div>
          </div>
        </div>
      </section>

      <div className="grid gap-4 lg:grid-cols-3">
        <Panel title="North direction">
          <dl className="divide-y divide-hairline text-sm">
            <Row k="Angle used" v={`${Math.round(d.north.angle)}° from image top`} />
            <Row k="Confirmed by you" v={d.north.confirmed ? fmtDate(d.north.confirmed_at) : "No"} />
            <Row k="Source" v={d.north.is_image_top ? "Top of the drawing" : "Set on the North step"} />
            <Row k="Site compass" v={d.north.site_check
              ? <span className={d.north.site_check.agrees ? "text-positive" : "text-major"}>{Math.round(d.north.site_check.compass_angle)}° ({d.north.site_check.difference_deg}° apart)</span>
              : <Link className="underline" href={`/projects/${projectId}/insights/post-move`}>Not recorded</Link>} />
          </dl>
        </Panel>
        <Panel title="Room detection">
          <div className="grid grid-cols-3 gap-3 p-4">
            <Stat label="Kept as AI drew" value={det.kept_unchanged} />
            <Stat label="Corrected" value={det.edited} />
            <Stat label="Added by you" value={det.added_by_user} />
          </div>
          <dl className="divide-y divide-hairline border-t border-hairline text-sm">
            <Row k="Detector" v={det.is_mock ? "Demo detector (mock)" : det.provider ?? "None (drawn by hand)"} />
            <Row k="AI rooms found" v={det.detected_rooms} />
            <Row k="AI rooms removed" v={det.removed} />
            <Row k="Average AI confidence" v={det.average_confidence != null ? `${Math.round(det.average_confidence * 100)}%` : "—"} />
          </dl>
          {det.low_confidence_unreviewed.length > 0 && (
            <p className="border-t border-hairline px-4 py-2.5 text-sm text-warning">Unreviewed low-confidence: {det.low_confidence_unreviewed.join(", ")}</p>
          )}
        </Panel>
        <Panel title="How sensitive is the result?">
          {sens ? (
            <div className="space-y-3 p-4 text-sm">
              <div>
                <p className="text-xs text-slate">Score if North is off by ±{sens.degrees}°</p>
                <SensitivityBar min={sens.score_min} max={sens.score_max} now={sens.score_now} />
              </div>
              <p className="text-ink-soft">
                {sens.rooms_changing_zone.length
                  ? <>Rooms that would change zone: {sens.rooms_changing_zone.map((r) => `${r.label} (${r.zone_now} → ${r.could_be.join("/")})`).join(", ")}.</>
                  : "No room changes zone within this range."}
              </p>
            </div>
          ) : <p className="p-4 text-sm text-slate">Not available for this plan.</p>}
          {d.uncertainty.borderline_rooms.length > 0 && (
            <div className="border-t border-hairline px-4 py-3 text-sm">
              <p className="text-xs text-slate">Rooms across two zones</p>
              <ul className="mt-1 space-y-0.5">{d.uncertainty.borderline_rooms.map((r) => (
                <li key={r.room_id}>{r.label}: {Math.round(r.share * 100)}% {r.zone}, {Math.round(r.second_share * 100)}% {r.second_zone}</li>
              ))}</ul>
            </div>
          )}
        </Panel>
      </div>

      <Panel title="AI Mistake Catcher on the analysed plan" aside={<span className="text-xs text-slate">{d.plan_checks.error} errors · {d.plan_checks.warning} warnings · {d.plan_checks.info} notes</span>}>
        <CheckList checks={d.plan_check_items} empty="No likely mistakes found." />
        <p className="border-t border-hairline px-4 py-2.5 text-xs text-slate">The same checks run live while you edit on the <Link className="underline" href={`/projects/${projectId}/verify`}>Verify</Link> step.</p>
      </Panel>
    </div>
  );
}

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return <div className="flex justify-between gap-3 px-4 py-2"><dt className="text-slate">{k}</dt><dd className="text-right">{v}</dd></div>;
}

function SensitivityBar({ min, max, now }: { min: number | null; max: number | null; now: number | null }) {
  if (min == null || max == null || now == null) return <p>—</p>;
  return (
    <div className="mt-1.5">
      <div className="relative h-2 rounded-full bg-paper">
        <div className="absolute h-2 rounded-full bg-warning/50" style={{ left: `${min}%`, width: `${Math.max(1, max - min)}%` }} />
        <div className="absolute -top-1 h-4 w-0.5 bg-ink" style={{ left: `${now}%` }} aria-hidden />
      </div>
      <p className="mt-1 flex justify-between text-xs text-slate"><span>{min}</span><span className="text-ink">now {now}</span><span>{max}</span></p>
    </div>
  );
}

const SEV = { error: { tone: "text-major", mark: "✕" }, warning: { tone: "text-warning", mark: "!" }, info: { tone: "text-slate", mark: "i" } };

export function CheckList({ checks, empty, onSelect }: { checks: PlanCheck[]; empty: string; onSelect?: (c: PlanCheck) => void }) {
  if (!checks.length) return <p className="px-4 py-3 text-sm text-positive">{empty}</p>;
  return (
    <ul className="divide-y divide-hairline text-sm">
      {checks.map((c, i) => (
        <li key={`${c.code}-${i}`} className="flex gap-3 px-4 py-2.5">
          <span aria-hidden className={`mt-0.5 w-3 shrink-0 text-center font-medium ${SEV[c.severity].tone}`}>{SEV[c.severity].mark}</span>
          <div className="min-w-0">
            {onSelect && c.subject_ids.length ? (
              <button className="text-left font-medium underline-offset-2 hover:underline" onClick={() => onSelect(c)}>{c.title}</button>
            ) : <p className="font-medium">{c.title}</p>}
            <p className="text-ink-soft">{c.message}</p>
            <p className="text-xs text-slate">{c.hint}</p>
          </div>
        </li>
      ))}
    </ul>
  );
}
