"use client";
import { useEffect, useRef, useState } from "react";
import { ErrorNote, Spinner } from "@/components/ui";
import { api } from "@/services/api";
import type { Report, ReportLanguage } from "@/types/api";

export const LANGUAGES: { value: ReportLanguage; label: string; hint: string; name: string }[] = [
  { value: "en", label: "English", hint: "English PDF", name: "English" },
  { value: "mr", label: "मराठी", hint: "Marathi PDF", name: "Marathi" },
];
export const languageLabel = (l: ReportLanguage | undefined) => LANGUAGES.find((x) => x.value === (l ?? "en"))!.label;

const POLL_MS = 1500;
const TIMEOUT_MS = 3 * 60 * 1000;

/** Opens the signed URL; the API answers with Content-Disposition: attachment, so the page stays put. */
function startDownload(url: string) {
  const a = document.createElement("a");
  a.href = url;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

/**
 * Download PDF → choose English or मराठी → the report is generated in that language → it downloads.
 * A ready report for the current analysis in the chosen language is reused instead of regenerated.
 * If generation fails the error is shown here; it never falls back to another language.
 */
export function DownloadPdfDialog({ projectId, analysisId, reports, onClose, onChanged }: {
  projectId: string; analysisId: string | null; reports: Report[]; onClose: () => void; onChanged: () => void;
}) {
  const [busy, setBusy] = useState<ReportLanguage | null>(null);
  const [actionPlan, setActionPlan] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const alive = useRef(true);
  const firstButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    alive.current = true;
    firstButton.current?.focus();
    return () => { alive.current = false; };
  }, []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape" && !busy) onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, onClose]);

  async function waitUntilReady(id: string): Promise<Report> {
    const started = Date.now();
    for (;;) {
      const r = await api.report(id);
      if (r.status === "ready" || r.status === "failed") return r;
      if (!alive.current) throw new Error("cancelled");
      if (Date.now() - started > TIMEOUT_MS) throw new Error("The PDF is taking longer than expected. It will appear in the list when ready.");
      await new Promise((res) => setTimeout(res, POLL_MS));
    }
  }

  async function choose(language: ReportLanguage) {
    const name = LANGUAGES.find((l) => l.value === language)!.name;
    setBusy(language); setError(null);
    try {
      // Reuse only a report made with the same options: the action plan reflects current Insights settings,
      // so a fresh one is generated when it is included.
      const existing = !actionPlan && reports.find((r) => r.status === "ready" && (r.language ?? "en") === language
        && r.analysis_id === analysisId && !r.action_plan);
      // Re-read even a cached report: download links are signed and expire.
      const report = existing ? await api.report(existing.id)
        : await waitUntilReady((await api.createReport(projectId, language, actionPlan)).id);
      onChanged();
      if (report.status !== "ready" || !report.download_url) {
        throw new Error(report.error ?? `The ${name} PDF could not be generated.`);
      }
      startDownload(report.download_url);
      if (alive.current) onClose();
    } catch (e) {
      if (alive.current && !(e instanceof Error && e.message === "cancelled")) setError(e);
    } finally {
      if (alive.current) setBusy(null);
    }
  }

  const busyName = busy ? LANGUAGES.find((l) => l.value === busy)!.name : null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4"
         onMouseDown={(e) => { if (e.target === e.currentTarget && !busy) onClose(); }}>
      <div role="dialog" aria-modal="true" aria-labelledby="pdf-dialog-title" className="panel w-full max-w-sm p-5 shadow-lg">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id="pdf-dialog-title" className="font-medium text-ink">Download PDF</h2>
            <p className="mt-0.5 text-sm text-slate">Select report language</p>
          </div>
          <button className="btn-quiet -mr-2 -mt-1 px-2 py-1" onClick={onClose} disabled={!!busy} aria-label="Close">✕</button>
        </div>
        <div className="mt-4 grid gap-2">
          {LANGUAGES.map((l, i) => (
            <button key={l.value} ref={i === 0 ? firstButton : undefined} lang={l.value}
                    className="btn-secondary justify-between py-3 text-left" onClick={() => choose(l.value)}
                    disabled={!!busy}>
              <span className="text-base">{l.label}</span>
              <span className="flex items-center gap-2 text-xs text-slate" lang="en">
                {busy === l.value ? <><Spinner className="text-brass" /> Generating</> : l.hint}
              </span>
            </button>
          ))}
        </div>
        <label className="mt-4 flex items-start gap-2 text-sm text-ink-soft">
          <input type="checkbox" className="mt-0.5" checked={actionPlan} onChange={(e) => setActionPlan(e.target.checked)} disabled={!!busy} />
          <span>Include <b className="font-medium text-ink">personal action plan</b> <span lang="mr" className="text-slate">(वैयक्तिक कृती योजना)</span>
            <span className="block text-xs text-slate">What moves the score, how reliable it is, and, if set up in Insights, the remedies that fit, stage advice and family priorities.</span></span>
        </label>
        {busy && <p className="mt-3 text-xs text-slate" role="status">Generating the {busyName} PDF. This usually takes a few seconds.</p>}
        {error != null && <div className="mt-3"><ErrorNote error={error} /></div>}
      </div>
    </div>
  );
}
