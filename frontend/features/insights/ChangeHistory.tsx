"use client";
import { useEffect, useState } from "react";
import { ErrorNote, Loading, scoreTone } from "@/components/ui";
import { api } from "@/services/api";
import type { Comparison } from "@/types/insights";
import { BucketDot, fmtDate, InsightState, Panel, Pill, ToolIntro, useInsight } from "./shared";

export function ChangeHistory({ projectId }: { projectId: string }) {
  const { data, error, noAnalysis, reload } = useInsight(() => api.history(projectId), [projectId]);
  const [pair, setPair] = useState<[string, string] | null>(null);
  const [cmp, setCmp] = useState<Comparison | null>(null);
  const [cmpError, setCmpError] = useState<unknown>(null);
  const versions = data?.versions ?? [];

  useEffect(() => {
    if (versions.length >= 2 && !pair) setPair([versions[versions.length - 2].id, versions[versions.length - 1].id]);
  }, [versions, pair]);
  useEffect(() => {
    if (!pair) return;
    setCmp(null); setCmpError(null);
    api.compareVersions(projectId, pair[0], pair[1]).then(setCmp).catch(setCmpError);
  }, [pair, projectId]);

  if (!data) return <InsightState projectId={projectId} error={error} noAnalysis={noAnalysis} reload={reload} />;
  if (!versions.length) return <div className="space-y-5"><ToolIntro slug="history" /><p className="text-sm text-slate">No analyses yet.</p></div>;
  const max = 100;

  return (
    <div className="space-y-5">
      <ToolIntro slug="history" />
      <Panel title="Versions" aside={<span className="text-xs text-slate">each run of the analysis is kept</span>}>
        <div className="flex items-end gap-2 overflow-x-auto px-4 pt-4" role="img" aria-label={`Scores: ${versions.map((v) => `v${v.version} ${v.overall_score}`).join(", ")}`}>
          {versions.map((v) => (
            <div key={v.id} className="flex min-w-[44px] flex-col items-center gap-1">
              <span className={`text-xs ${scoreTone(v.overall_score)}`}>{v.overall_score ?? "—"}</span>
              <div className={`w-7 rounded-t ${v.is_latest ? "bg-ink" : "bg-slate/40"}`} style={{ height: `${Math.max(4, ((v.overall_score ?? 0) / max) * 110)}px` }} />
              <span className="text-[11px] text-slate">v{v.version}</span>
            </div>
          ))}
        </div>
        <div className="overflow-x-auto">
          <table className="mt-3 w-full min-w-[640px] text-sm">
            <thead className="text-left text-xs text-slate"><tr className="border-y border-hairline">
              <th className="px-4 py-2 font-normal">Version</th><th className="px-2 font-normal">Run on</th><th className="px-2 font-normal">Score</th>
              <th className="px-2 font-normal">Issues</th><th className="px-2 font-normal">Rooms</th><th className="px-2 font-normal">North</th><th className="px-4 font-normal">Compare</th></tr></thead>
            <tbody className="divide-y divide-hairline">
              {[...versions].reverse().map((v) => (
                <tr key={v.id}>
                  <td className="px-4 py-2">v{v.version} {v.is_latest && <Pill tone="ink">latest</Pill>}<span className="block text-xs text-slate">{v.plan_file}</span></td>
                  <td className="px-2 py-2">{fmtDate(v.created_at)}</td>
                  <td className={`px-2 py-2 font-medium ${scoreTone(v.overall_score)}`}>{v.overall_score ?? "—"}</td>
                  <td className="px-2 py-2">{(v.counts?.major ?? 0)} major · {(v.counts?.warning ?? 0)} warn.</td>
                  <td className="px-2 py-2">{v.rooms}</td>
                  <td className="px-2 py-2">{Math.round(v.north_angle)}°</td>
                  <td className="px-4 py-2 text-xs">
                    <label className="mr-3"><input type="radio" name="old" checked={pair?.[0] === v.id} onChange={() => setPair([v.id, pair?.[1] ?? v.id])} /> from</label>
                    <label><input type="radio" name="new" checked={pair?.[1] === v.id} onChange={() => setPair([pair?.[0] ?? v.id, v.id])} /> to</label>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      {versions.length < 2 ? (
        <p className="text-sm text-slate">Re-run the analysis after changing the plan or North to start comparing versions.</p>
      ) : cmpError ? <ErrorNote error={cmpError} /> : !cmp ? <Loading label="Comparing" /> : pair && pair[0] === pair[1] ? (
        <p className="text-sm text-slate">Pick two different versions to compare.</p>
      ) : <CompareView c={cmp} versions={Object.fromEntries(versions.map((v) => [v.id, v.version]))} />}
    </div>
  );
}

function CompareView({ c, versions }: { c: Comparison; versions: Record<string, number> }) {
  const delta = c.score_delta;
  const f = c.findings;
  return (
    <div className="space-y-4">
      <div className="panel flex flex-wrap items-center gap-6 p-5">
        <div><p className="text-xs text-slate">v{versions[c.old.id]}</p><p className={`font-display text-4xl ${scoreTone(c.old.overall_score)}`}>{c.old.overall_score ?? "—"}</p></div>
        <span className="text-2xl text-slate" aria-hidden>→</span>
        <div><p className="text-xs text-slate">v{versions[c.new.id]}</p><p className={`font-display text-4xl ${scoreTone(c.new.overall_score)}`}>{c.new.overall_score ?? "—"}</p></div>
        {delta != null && <Pill tone={delta > 0 ? "positive" : delta < 0 ? "major" : "neutral"} className="text-sm">{delta > 0 ? "+" : ""}{delta} points</Pill>}
        {c.north_changed && <span className="text-sm text-ink-soft">North changed {Math.round(c.old.north_angle)}° → {Math.round(c.new.north_angle)}°</span>}
        <div className="ml-auto flex flex-wrap gap-x-5 gap-y-1 text-sm">
          {c.categories.map((x) => (
            <span key={x.category} className="text-ink-soft">{x.category} <span className={x.delta == null ? "text-slate" : x.delta > 0 ? "text-positive" : x.delta < 0 ? "text-major" : "text-slate"}>
              {x.delta == null ? "n/a" : `${x.delta > 0 ? "+" : ""}${x.delta}`}</span></span>
          ))}
        </div>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Group title="Improved" tone="positive" rows={f.improved.map((x) => ({ k: x.subject, a: x.old, b: x.new, bucket: x.new_bucket }))} />
        <Group title="Got worse" tone="major" rows={f.worsened.map((x) => ({ k: x.subject, a: x.old, b: x.new, bucket: x.new_bucket }))} />
        <Group title="Issues resolved" tone="positive" rows={f.resolved.map((x) => ({ k: x.subject, a: x.finding, bucket: x.bucket }))} />
        <Group title="New issues" tone="major" rows={f.new_issues.map((x) => ({ k: x.subject, a: x.finding, bucket: x.bucket }))} />
      </div>
      <Panel title="Rooms">
        <dl className="grid gap-x-6 gap-y-2 p-4 text-sm sm:grid-cols-2">
          <div><dt className="text-xs text-slate">Changed zone</dt><dd>{c.rooms.moved_zone.length ? c.rooms.moved_zone.map((m) => `${m.room}: ${m.old_zone} → ${m.new_zone}`).join("; ") : "None"}</dd></div>
          <div><dt className="text-xs text-slate">Changed type</dt><dd>{c.rooms.retyped.length ? c.rooms.retyped.map((m) => `${m.room}: ${m.old_type} → ${m.new_type}`).join("; ") : "None"}</dd></div>
          <div><dt className="text-xs text-slate">Added</dt><dd>{c.rooms.added.join(", ") || "None"}</dd></div>
          <div><dt className="text-xs text-slate">Removed</dt><dd>{c.rooms.removed.join(", ") || "None"}</dd></div>
        </dl>
        <p className="border-t border-hairline px-4 py-2 text-xs text-slate">{f.unchanged} findings unchanged. Rooms are matched by name.</p>
      </Panel>
    </div>
  );
}

function Group({ title, tone, rows }: { title: string; tone: "positive" | "major"; rows: { k: string; a: string; b?: string; bucket: import("@/types/api").Bucket }[] }) {
  return (
    <Panel title={<span className="flex items-center gap-2">{title} <Pill tone={rows.length ? tone : "neutral"}>{rows.length}</Pill></span>}>
      {rows.length ? (
        <ul className="divide-y divide-hairline text-sm">
          {rows.map((r, i) => (
            <li key={`${r.k}-${i}`} className="flex gap-2 px-4 py-2.5"><BucketDot bucket={r.bucket} />
              <div><p className="font-medium">{r.k}</p>{r.b ? <><p className="text-slate line-through decoration-slate/40">{r.a}</p><p className="text-ink-soft">{r.b}</p></> : <p className="text-ink-soft">{r.a}</p>}</div>
            </li>
          ))}
        </ul>
      ) : <p className="px-4 py-3 text-sm text-slate">None.</p>}
    </Panel>
  );
}
