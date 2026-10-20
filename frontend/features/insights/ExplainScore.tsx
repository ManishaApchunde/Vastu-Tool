"use client";
import { useState } from "react";
import { scoreTone } from "@/components/ui";
import { api } from "@/services/api";
import { InsightState, Panel, Pill, StaleNote, Stat, ToolIntro, useInsight } from "./shared";

const STATUS_TONE = { preferred: "positive", acceptable: "positive", issue: "major", not_evaluated: "neutral" } as const;

export function ExplainScore({ projectId }: { projectId: string }) {
  const { data: d, error, noAnalysis, reload } = useInsight(() => api.explain(projectId), [projectId]);
  const [open, setOpen] = useState<string | null>(null);
  if (!d) return <InsightState projectId={projectId} error={error} noAnalysis={noAnalysis} reload={reload} />;
  const scored = d.categories.filter((c) => c.score != null);

  return (
    <div className="space-y-5">
      <ToolIntro slug="explain" />
      <StaleNote stale={d.stale} projectId={projectId} />
      <div className="panel grid gap-5 p-5 sm:grid-cols-4">
        <Stat label="Official score" value={<>{d.overall ?? "—"}<span className="text-base text-slate"> / 100</span></>} tone={scoreTone(d.overall)}
          sub={d.overall_exact != null ? `exactly ${d.overall_exact}` : undefined} />
        <Stat label="If every issue were resolved" value={d.ceiling_if_all_issues_resolved ?? "—"} sub="the ceiling for this plan" />
        <Stat label="Rules that applied" value={`${d.rules.triggered}`} sub={`of ${d.rules.approved_in_rule_set} approved rules`} />
        <Stat label="Not scored" value={d.not_scored.length} sub="rooms without a matching rule" />
      </div>

      <Panel title="How the number is built">
        <ol className="list-decimal space-y-1.5 py-3 pl-9 pr-4 text-sm text-ink-soft">
          {d.steps.map((s) => <li key={s}>{s}</li>)}
        </ol>
        <div className="border-t border-hairline px-4 py-3">
          <p className="mb-2 text-xs text-slate">Each category's share of the final score</p>
          <div className="flex h-7 w-full overflow-hidden rounded" role="img"
            aria-label={scored.map((c) => `${c.label} ${c.contribution} points`).join(", ")}>
            {scored.map((c, i) => (
              <div key={c.category} title={`${c.label}: ${c.score}/100 × ${Math.round((c.share_of_overall ?? 0) * 100)}% = ${c.contribution}`}
                className={`flex items-center justify-center text-[11px] text-white ${["bg-ink", "bg-ink-soft", "bg-slate", "bg-ink/70", "bg-slate/70"][i % 5]}`}
                style={{ width: `${(c.share_of_overall ?? 0) * 100}%` }}>
                <span className="truncate px-1">{c.label} {c.contribution}</span>
              </div>
            ))}
          </div>
          <p className="mt-2 text-xs text-slate">
            {scored.map((c) => `${c.label} ${c.score} × ${Math.round((c.share_of_overall ?? 0) * 100)}%`).join(" + ")} = {d.overall_exact}
          </p>
        </div>
      </Panel>

      {d.drags.length > 0 && (
        <Panel title="What pulls the score down most" aside={<span className="text-xs text-slate">gain if the rule passed</span>}>
          <ol className="divide-y divide-hairline text-sm">
            {d.drags.map((g) => (
              <li key={g.finding_id} className="grid grid-cols-[1fr_auto] gap-3 px-4 py-2.5">
                <div>
                  <p>{g.finding}</p>
                  <p className="text-xs text-slate">{g.category} · {g.severity} severity{g.structural_only ? " · fixing the placement needs structural change" : ""}</p>
                </div>
                <span className="self-center font-display text-xl text-positive">+{g.overall_gain}</span>
              </li>
            ))}
          </ol>
          <p className="border-t border-hairline px-4 py-2.5 text-xs text-slate">{d.note}</p>
        </Panel>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        {d.categories.map((c) => (
          <Panel key={c.category}
            title={<span className="flex items-center gap-2">{c.label} <span className="text-xs font-normal text-slate">weight {Math.round(c.category_weight * 100)}%</span></span>}
            aside={<span className={`font-display text-xl ${scoreTone(c.score)}`}>{c.score ?? "n/a"}</span>}>
            {c.items.length ? (
              <table className="w-full text-sm">
                <thead className="text-left text-xs text-slate">
                  <tr><th className="px-4 py-1.5 font-normal">Finding</th><th className="px-2 font-normal">Weight</th><th className="px-2 font-normal">Points</th><th className="px-4 text-right font-normal">Earned</th></tr>
                </thead>
                <tbody className="divide-y divide-hairline">
                  {c.items.map((it) => (
                    <tr key={it.finding_id} className="cursor-pointer align-top hover:bg-paper/60" onClick={() => setOpen(open === it.finding_id ? null : it.finding_id)}>
                      <td className="px-4 py-2">
                        <span className="flex flex-wrap items-center gap-1.5">{it.subject} <Pill tone={STATUS_TONE[it.status as keyof typeof STATUS_TONE] ?? "neutral"}>{it.status}{it.status === "issue" ? ` · ${it.severity}` : ""}</Pill></span>
                        {open === it.finding_id && (
                          <span className="mt-1 block text-xs text-ink-soft">{it.finding}{it.explanation ? ` ${it.explanation}` : ""}{it.rule_code ? ` (rule ${it.rule_code})` : ""}</span>
                        )}
                      </td>
                      <td className="px-2 py-2">{it.weight}</td>
                      <td className="px-2 py-2">× {it.points}</td>
                      <td className="px-4 py-2 text-right">{it.earned}{it.lost > 0 && <span className="block text-xs text-major">−{it.lost}</span>}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot><tr className="border-t border-hairline text-xs text-slate"><td className="px-4 py-2" colSpan={3}>Earned ÷ possible</td><td className="px-4 py-2 text-right">{c.earned} / {c.possible}</td></tr></tfoot>
              </table>
            ) : <p className="px-4 py-3 text-sm text-slate">No scored findings: this category is left out of the overall score.</p>}
          </Panel>
        ))}
      </div>

      {d.not_scored.length > 0 && (
        <Panel title="Not scored">
          <ul className="divide-y divide-hairline text-sm">{d.not_scored.map((n) => <li key={n.subject} className="px-4 py-2 text-ink-soft">{n.finding}</li>)}</ul>
        </Panel>
      )}
    </div>
  );
}
