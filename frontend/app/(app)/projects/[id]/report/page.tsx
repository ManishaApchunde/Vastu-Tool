"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ErrorNote, Loading, Spinner } from "@/components/ui";
import { useProject } from "@/components/useProject";
import { ProjectHeader } from "@/features/ProjectHeader";
import { DownloadPdfDialog, languageLabel } from "@/features/report/DownloadPdfDialog";
import { VideoReport } from "@/features/report/VideoReport";
import { api } from "@/services/api";
import type { Report } from "@/types/api";

const SECTIONS = ["Cover and executive summary", "Property layout and directional assessment (annotated plan)",
  "Room-wise compliance overview", "Score breakdown and zone summary", "Room-by-room detailed analysis",
  "Positive findings, warnings and major issues", "Phase-wise remedial plan and remedy details",
  "Personal action plan (optional)", "Evaluation summary and next steps", "Disclaimer"];

export default function ReportPage() {
  const { id } = useParams<{ id: string }>();
  const { project, error: loadError, reload } = useProject(id);
  const [reports, setReports] = useState<Report[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [choosing, setChoosing] = useState(false);

  const load = useCallback(() => api.reports(id).then(setReports).catch(setError), [id]);
  useEffect(() => { load(); }, [load]);
  const pending = reports?.some((r) => r.status === "queued" || r.status === "running");
  useEffect(() => {
    if (!pending) return;
    const t = setInterval(load, 1500);
    return () => clearInterval(t);
  }, [pending, load]);

  async function retry(r: Report) {
    if (!r.job) return;
    try { await api.retryJob(r.job.id); await load(); } catch (e) { setError(e); }
  }

  if (loadError) return <ErrorNote error={loadError} onRetry={reload} />;
  if (!project || !reports) return <Loading />;
  const analysed = project.analysis_id != null;

  return (
    <div>
      <ProjectHeader project={project} current="report" title="PDF report">
        <button className="btn-primary" onClick={() => setChoosing(true)} disabled={!analysed}>Download PDF</button>
      </ProjectHeader>
      <ErrorNote error={error} />
      {choosing && (
        <DownloadPdfDialog projectId={id} analysisId={project.analysis_id} reports={reports}
                           onClose={() => setChoosing(false)} onChanged={load} />
      )}
      {!analysed && <p className="text-slate">Run the analysis before generating a report. <Link className="text-ink underline" href={`/projects/${id}/analysis`}>Go to analysis</Link></p>}
      <div className="mt-4 grid gap-6 lg:grid-cols-[1fr_300px]">
        <section className="panel">
          <h2 className="border-b border-hairline px-4 py-3 font-medium">Reports</h2>
          {reports.length === 0 ? <p className="p-4 text-sm text-slate">No reports yet.</p> : (
            <ul className="divide-y divide-hairline">
              {reports.map((r) => (
                <li key={r.id} className="flex flex-wrap items-center gap-3 px-4 py-3 text-sm">
                  <div className="min-w-0 flex-1">
                    <p>Vastu report · <span lang={r.language ?? "en"}>{languageLabel(r.language)}</span>{r.action_plan ? " · with action plan" : ""} · {new Date(r.created_at).toLocaleString()}</p>
                    {r.status === "failed" && <p className="text-major">{r.error ?? "Report generation failed."}</p>}
                  </div>
                  {r.status === "ready" && r.download_url && <a className="btn-secondary" href={r.download_url} target="_blank" rel="noopener">Download PDF</a>}
                  {(r.status === "queued" || r.status === "running") && <span className="flex items-center gap-2 text-brass"><Spinner /> Generating</span>}
                  {r.status === "failed" && (r.job?.can_retry
                    ? <button className="btn-secondary" onClick={() => retry(r)}>Retry</button>
                    : <span className="text-xs text-slate">Retries used up. Generate a new report.</span>)}
                </li>
              ))}
            </ul>
          )}
        </section>
        <aside className="panel p-4 text-sm">
          <p className="font-medium">What's in the report</p>
          <ol className="mt-2 list-decimal space-y-0.5 pl-5 text-ink-soft">{SECTIONS.map((s) => <li key={s}>{s}</li>)}</ol>
          <p className="mt-3 text-xs text-slate">Available in English and मराठी (Marathi): choose the language when you download. Both use the same analysis, scores and remedies. Built from the stored analysis data, not from AI-written text. Length depends on the number of rooms. Download links expire after a short time; reopen this page for a fresh one.</p>
        </aside>
      </div>
      <VideoReport projectId={id} analysed={analysed} />
    </div>
  );
}
