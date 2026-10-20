"use client";
import { useState } from "react";
import { ErrorNote, Spinner } from "@/components/ui";
import { api } from "@/services/api";
import type { ExpertReview as Review } from "@/types/insights";
import { fmtDate, InsightState, Panel, Pill, ToolIntro, useInsight } from "./shared";

const ROLES = [["vastu_consultant", "Vastu consultant"], ["architect", "Architect"], ["engineer", "Structural engineer"], ["other", "Other"]] as const;
const STATUS = { open: { label: "Waiting for reply", tone: "brass" }, submitted: { label: "Reply received", tone: "positive" },
  revoked: { label: "Link revoked", tone: "neutral" } } as const;
const VERDICT = { agree: "Agrees with the analysis", agree_with_changes: "Agrees, with changes", disagree: "Disagrees" };

export function ExpertReview({ projectId }: { projectId: string }) {
  const { data, error, noAnalysis, reload } = useInsight(() => Promise.all([api.expertReviews(projectId), api.findings(projectId)]), [projectId]);
  const [form, setForm] = useState({ expert_name: "", expert_role: "vastu_consultant", message: "", valid_days: 14, include_contact: false });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const [link, setLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  if (!data) return <InsightState projectId={projectId} error={error} noAnalysis={noAnalysis} reload={reload} />;
  const [reviews, findings] = data;
  const labelOf = Object.fromEntries(findings.map((f) => [f.id, f]));

  async function create() {
    setBusy(true); setErr(null); setLink(null); setCopied(false);
    try {
      const r = await api.createExpertReview(projectId, { ...form, expert_name: form.expert_name || null, message: form.message || null });
      setLink(`${window.location.origin}/review/${r.token}`);
      reload();
    } catch (e) { setErr(e); } finally { setBusy(false); }
  }
  async function revoke(r: Review) {
    if (!confirm("Revoke this link? The expert will no longer be able to open it.")) return;
    try { await api.revokeExpertReview(projectId, r.id); reload(); } catch (e) { setErr(e); }
  }

  return (
    <div className="space-y-5">
      <ToolIntro slug="expert-review" />
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[360px_minmax(0,1fr)]">
        <Panel title="Create a review link" className="self-start">
          <div className="space-y-4 p-4 text-sm">
            <p className="text-ink-soft">The expert gets a read-only pack: the verified plan with zones, every finding with its rule and remedy, the trust passport, open plan checks, your constraints, and a list of questions to settle on site. They can reply per finding without an account.</p>
            <div><label className="label" htmlFor="xr-name">Expert's name</label>
              <input id="xr-name" className="field" value={form.expert_name} maxLength={200} onChange={(e) => setForm({ ...form, expert_name: e.target.value })} /></div>
            <div><label className="label" htmlFor="xr-role">Role</label>
              <select id="xr-role" className="field" value={form.expert_role} onChange={(e) => setForm({ ...form, expert_role: e.target.value })}>
                {ROLES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
            <div><label className="label" htmlFor="xr-msg">Message</label>
              <textarea id="xr-msg" className="field min-h-[80px]" maxLength={2000} placeholder="What would you like them to look at?" value={form.message}
                onChange={(e) => setForm({ ...form, message: e.target.value })} /></div>
            <div className="flex items-center gap-2"><label htmlFor="xr-days" className="text-ink-soft">Link valid for</label>
              <select id="xr-days" className="rounded border border-hairline bg-white px-2 py-1" value={form.valid_days} onChange={(e) => setForm({ ...form, valid_days: Number(e.target.value) })}>
                {[3, 7, 14, 30, 60].map((n) => <option key={n} value={n}>{n} days</option>)}</select></div>
            <label className="flex items-start gap-2 text-ink-soft"><input type="checkbox" className="mt-0.5" checked={form.include_contact}
              onChange={(e) => setForm({ ...form, include_contact: e.target.checked })} /> Include the customer's name and address</label>
            <ErrorNote error={err} />
            <button className="btn-primary w-full" onClick={create} disabled={busy}>{busy && <Spinner />} Create link</button>
            {link && (
              <div className="space-y-2 rounded border border-positive/30 bg-positive-light p-3">
                <p className="text-xs text-positive">Link created. Copy it now: for security it is shown only once.</p>
                <input readOnly className="field text-xs" value={link} onFocus={(e) => e.currentTarget.select()} aria-label="Review link" />
                <div className="flex gap-2">
                  <button className="btn-secondary" onClick={() => { navigator.clipboard?.writeText(link).then(() => setCopied(true)); }}>{copied ? "Copied" : "Copy link"}</button>
                  <a className="btn-secondary" target="_blank" rel="noopener" href={`https://wa.me/?text=${encodeURIComponent(`Please review this Vastu analysis: ${link}`)}`}>Share on WhatsApp</a>
                </div>
              </div>
            )}
          </div>
        </Panel>

        <div className="space-y-4">
          {reviews.length === 0 && <p className="panel p-4 text-sm text-slate">No review links yet.</p>}
          {reviews.map((r) => {
            const st = STATUS[r.status];
            return (
              <Panel key={r.id} title={<span>{r.expert_name || "Unnamed expert"} <span className="text-xs font-normal text-slate">{ROLES.find((x) => x[0] === r.expert_role)?.[1]}</span></span>}
                aside={<Pill tone={st.tone}>{st.label}</Pill>}>
                <div className="space-y-3 p-4 text-sm">
                  <p className="text-xs text-slate">Created {fmtDate(r.created_at)} · expires {fmtDate(r.expires_at)}{r.include_contact ? " · includes contact details" : ""}</p>
                  {r.message && <p className="text-ink-soft">“{r.message}”</p>}
                  {r.feedback && (
                    <div className="space-y-2 rounded bg-paper p-3">
                      <p className="font-medium">{VERDICT[r.feedback.verdict]}</p>
                      <p className="whitespace-pre-line text-ink-soft">{r.feedback.summary}</p>
                      {r.feedback.north_confirmed != null && <p className="text-xs">North on site: {r.feedback.north_confirmed ? "confirmed" : <span className="text-major">not confirmed</span>}</p>}
                      {Object.entries(r.feedback.items).filter(([, v]) => v.agree != null || v.comment).map(([fid, v]) => (
                        <div key={fid} className="border-t border-hairline pt-2">
                          <p className="text-xs text-slate">{labelOf[fid]?.subject_label ?? "Finding"}: {labelOf[fid]?.finding ?? ""}</p>
                          <p>{v.agree === true ? <span className="text-positive">Agrees.</span> : v.agree === false ? <span className="text-major">Disagrees.</span> : null} {v.comment}</p>
                        </div>
                      ))}
                      <p className="text-xs text-slate">Signed {r.reviewer_signature} · {fmtDate(r.submitted_at)}</p>
                    </div>
                  )}
                  <p className="text-xs text-slate">Expert replies are kept for you to act on; they never change the analysis by themselves.</p>
                  {r.status !== "revoked" && <button className="btn-quiet px-0 text-xs text-major" onClick={() => revoke(r)}>Revoke link</button>}
                </div>
              </Panel>
            );
          })}
        </div>
      </div>
    </div>
  );
}
