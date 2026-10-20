"use client";
import { useEffect, useState } from "react";
import { Mark } from "@/components/AppShell";
import { PlanCanvas } from "@/components/PlanCanvas";
import { BUCKET_STYLE, ErrorNote, Loading, Spinner, scoreTone } from "@/components/ui";
import { api } from "@/services/api";
import type { ExpertReview, ReviewPack } from "@/types/insights";
import { BucketDot, fmtDate, LEVEL_TONE, Panel, Pill } from "./shared";

type Item = { agree: boolean | null; comment: string };

export function ReviewPackView({ token }: { token: string }) {
  const [data, setData] = useState<{ review: ExpertReview; pack: ReviewPack } | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [items, setItems] = useState<Record<string, Item>>({});
  const [verdict, setVerdict] = useState<"agree" | "agree_with_changes" | "disagree">("agree_with_changes");
  const [summary, setSummary] = useState("");
  const [north, setNorth] = useState<"" | "yes" | "no">("");
  const [signature, setSignature] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState<string | null>(null);
  const [sendError, setSendError] = useState<unknown>(null);

  useEffect(() => {
    api.publicReview(token).then((d) => {
      setData(d);
      const fb = d.review.feedback;
      if (fb) {
        setVerdict(fb.verdict); setSummary(fb.summary); setNorth(fb.north_confirmed == null ? "" : fb.north_confirmed ? "yes" : "no");
        setItems(Object.fromEntries(Object.entries(fb.items).map(([k, v]) => [k, { agree: v.agree, comment: v.comment ?? "" }])));
        setSignature(d.review.reviewer_signature ?? "");
      } else if (d.review.expert_name) setSignature(d.review.expert_name);
    }).catch(setError);
  }, [token]);

  async function submit() {
    setBusy(true); setSendError(null);
    try {
      const r = await api.submitReview(token, {
        verdict, summary, signature, north_confirmed: north === "" ? null : north === "yes",
        items: Object.fromEntries(Object.entries(items).filter(([, v]) => v.agree != null || v.comment.trim())
          .map(([k, v]) => [k, { agree: v.agree, comment: v.comment.trim() || null }])),
      });
      setSent(r.submitted_at);
    } catch (e) { setSendError(e); } finally { setBusy(false); }
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-hairline bg-white">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-2 px-5 font-display text-lg"><Mark /> Vastu review pack</div>
      </header>
      <main className="mx-auto max-w-6xl space-y-6 px-5 py-8">
        {error ? <ErrorNote error={error} /> : !data ? <Loading label="Opening the review pack" /> : (() => {
          const { pack: p, review: r } = data;
          const a = p.analysis;
          const set = (id: string, patch: Partial<Item>) => setItems({ ...items, [id]: { ...(items[id] ?? { agree: null, comment: "" }), ...patch } });
          return (
            <>
              <div className="flex flex-wrap items-end justify-between gap-4">
                <div>
                  <p className="text-sm text-slate">Review requested{r.expert_name ? ` from ${r.expert_name}` : ""} · link valid until {fmtDate(r.expires_at)}</p>
                  <h1 className="page-title">{p.project.name}</h1>
                  <p className="text-sm text-ink-soft">{[p.project.property_type?.replace("_", " "), p.project.built_up_area_sqft ? `${p.project.built_up_area_sqft.toLocaleString()} sq ft` : null,
                    p.project.client_name, p.project.address].filter(Boolean).join(" · ")}</p>
                </div>
                <div className="text-right">
                  <p className="text-xs text-slate">Score under {a.rule_set.name} v{a.rule_set.version}</p>
                  <p className={`font-display text-5xl ${scoreTone(a.overall_score)}`}>{a.overall_score ?? "—"}<span className="text-lg text-slate"> / 100</span></p>
                </div>
              </div>
              {p.message && <blockquote className="panel border-l-4 border-l-ink p-4 text-sm">“{p.message}”<span className="block text-xs text-slate">from the homeowner</span></blockquote>}

              <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
                <section className="panel p-4">
                  <PlanCanvas imageUrl={p.plan.image_url} width={p.plan.image_width} height={p.plan.image_height} zones={p.plan.zones}
                    centre={p.plan.centre} northAngle={a.north_angle} openings={p.plan.openings}
                    rooms={p.plan.rooms.map((x) => ({ id: x.id, label: x.label, polygon: x.polygon, sublabel: x.zone_name ?? undefined, fill: BUCKET_STYLE[x.worst_bucket].fill }))} />
                  <p className="mt-2 text-xs text-slate">North at {Math.round(a.north_angle)}° clockwise from the top of the drawing. Rooms are tinted by their worst finding.</p>
                </section>
                <div className="space-y-4">
                  <Panel title="Trust passport" aside={<Pill tone={LEVEL_TONE[p.passport.level]} className="capitalize">{p.passport.level}</Pill>}>
                    <ul className="space-y-1.5 p-4 text-sm">{p.passport.reasons.map((x) => <li key={x.text} className="flex gap-2"><span aria-hidden className={x.severity === "critical" ? "text-major" : "text-warning"}>!</span>{x.text}</li>)}
                      {!p.passport.reasons.length && <li className="text-positive">No concerns raised.</li>}</ul>
                  </Panel>
                  <Panel title="Questions for you">
                    {p.questions.length ? <ol className="list-decimal space-y-1.5 py-3 pl-9 pr-4 text-sm">{p.questions.map((q) => <li key={q}>{q}</li>)}</ol>
                      : <p className="p-4 text-sm text-slate">No specific questions.</p>}
                  </Panel>
                  <Panel title="Household">
                    <dl className="divide-y divide-hairline text-sm">
                      <div className="flex justify-between px-4 py-2"><dt className="text-slate">Ownership</dt><dd>{p.household.constraints.ownership}</dd></div>
                      <div className="flex justify-between px-4 py-2"><dt className="text-slate">Budget</dt><dd>{p.household.constraints.budget}</dd></div>
                      <div className="flex justify-between px-4 py-2"><dt className="text-slate">Civil / services work</dt><dd>{p.household.constraints.allow_structural ? "yes" : "no"} / {p.household.constraints.allow_services ? "yes" : "no"}</dd></div>
                      {p.household.construction_stage && <div className="flex justify-between px-4 py-2"><dt className="text-slate">Stage</dt><dd>{p.household.construction_stage.label}</dd></div>}
                      {p.household.family && p.household.family.members.length > 0 && <div className="flex justify-between gap-3 px-4 py-2"><dt className="text-slate">Family</dt><dd className="text-right">{p.household.family.members.join(", ").replaceAll("_", " ")}</dd></div>}
                    </dl>
                  </Panel>
                </div>
              </div>

              {p.plan_checks.length > 0 && (
                <Panel title="Open plan checks">
                  <ul className="divide-y divide-hairline text-sm">{p.plan_checks.map((c, i) => <li key={i} className="px-4 py-2.5"><span className="font-medium">{c.title}.</span> <span className="text-ink-soft">{c.message}</span></li>)}</ul>
                </Panel>
              )}

              <Panel title="Findings" aside={<span className="text-xs text-slate">mark each one you agree or disagree with</span>}>
                <ul className="divide-y divide-hairline">
                  {p.findings.map((f) => {
                    const it = items[f.id] ?? { agree: null, comment: "" };
                    return (
                      <li key={f.id} className="grid gap-3 px-4 py-3 text-sm md:grid-cols-[minmax(0,1fr)_300px]">
                        <div className="flex gap-2"><BucketDot bucket={f.bucket} />
                          <div><p>{f.finding}</p>
                            <p className="text-xs text-slate">{BUCKET_STYLE[f.bucket].label} · {f.category}{f.zone_name ? ` · ${f.zone_name}` : ""}{f.rule_code ? ` · rule ${f.rule_code}` : ""}</p>
                            {f.remedy && <p className="mt-1 text-xs text-ink-soft">Remedy: {f.remedy.recommendation}</p>}</div></div>
                        <div className="space-y-1.5">
                          <div className="flex gap-1">
                            {([[true, "Agree"], [false, "Disagree"]] as const).map(([v, l]) => (
                              <button key={l} type="button" aria-pressed={it.agree === v} onClick={() => set(f.id, { agree: it.agree === v ? null : v })}
                                className={`rounded border px-2.5 py-1 text-xs ${it.agree === v ? (v ? "border-positive bg-positive text-white" : "border-major bg-major text-white") : "border-hairline bg-white"}`}>{l}</button>
                            ))}
                          </div>
                          <input className="field py-1.5 text-xs" placeholder="Comment (optional)" maxLength={2000} value={it.comment}
                            onChange={(e) => set(f.id, { comment: e.target.value })} aria-label={`Comment on: ${f.finding}`} />
                        </div>
                      </li>
                    );
                  })}
                </ul>
              </Panel>

              <Panel title="Your overall opinion">
                <div className="grid gap-4 p-4 text-sm md:grid-cols-2">
                  <div className="space-y-3">
                    <fieldset><legend className="label">Verdict</legend>
                      <div className="flex flex-wrap gap-1">{([["agree", "Agree"], ["agree_with_changes", "Agree with changes"], ["disagree", "Disagree"]] as const).map(([v, l]) => (
                        <button key={v} type="button" aria-pressed={verdict === v} onClick={() => setVerdict(v)}
                          className={`rounded border px-2.5 py-1 ${verdict === v ? "border-ink bg-ink text-white" : "border-hairline bg-white"}`}>{l}</button>))}</div></fieldset>
                    <fieldset><legend className="label">Is North correct on site?</legend>
                      <div className="flex gap-1">{([["yes", "Yes"], ["no", "No"], ["", "Not checked"]] as const).map(([v, l]) => (
                        <button key={v} type="button" aria-pressed={north === v} onClick={() => setNorth(v)}
                          className={`rounded border px-2.5 py-1 ${north === v ? "border-ink bg-ink text-white" : "border-hairline bg-white"}`}>{l}</button>))}</div></fieldset>
                    <div><label className="label" htmlFor="sig">Your name (signature)</label>
                      <input id="sig" className="field" value={signature} maxLength={200} onChange={(e) => setSignature(e.target.value)} /></div>
                  </div>
                  <div><label className="label" htmlFor="sum">Summary for the homeowner</label>
                    <textarea id="sum" className="field min-h-[150px]" maxLength={6000} value={summary} onChange={(e) => setSummary(e.target.value)} /></div>
                </div>
                <div className="flex flex-wrap items-center gap-3 border-t border-hairline px-4 py-3">
                  <button className="btn-primary" onClick={submit} disabled={busy || !summary.trim() || !signature.trim()}>{busy && <Spinner />} {r.feedback || sent ? "Update review" : "Send review"}</button>
                  {sent && <span className="text-sm text-positive">Sent {fmtDate(sent)}. Thank you.</span>}
                  <ErrorNote error={sendError} />
                </div>
              </Panel>
              <p className="max-w-4xl text-xs leading-relaxed text-slate">{a.rule_set.disclaimer}</p>
            </>
          );
        })()}
      </main>
    </div>
  );
}
