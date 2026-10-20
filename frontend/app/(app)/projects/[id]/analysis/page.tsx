"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { PlanCanvas } from "@/components/PlanCanvas";
import { BUCKET_STYLE, ErrorNote, Loading, Spinner } from "@/components/ui";
import { useProject } from "@/components/useProject";
import { FindingsPanel, PlanPanel, RemediesPanel, RoomTable, ScorePanel } from "@/features/analysis/Dashboard";
import { ProjectHeader } from "@/features/ProjectHeader";
import { api, ApiError } from "@/services/api";
import type { Analysis } from "@/types/api";

export default function AnalysisPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { project, error: loadError, reload } = useProject(id);
  const [analysis, setAnalysis] = useState<Analysis | null | undefined>(undefined);
  const [error, setError] = useState<unknown>(null);
  const [running, setRunning] = useState(false);
  const [reporting, setReporting] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);

  const loadAnalysis = useCallback(async () => {
    try { setAnalysis(await api.analysis(id)); }
    catch (e) {
      if (e instanceof ApiError && e.code === "no_analysis") setAnalysis(null);
      else setError(e);
    }
  }, [id]);
  useEffect(() => { loadAnalysis(); }, [loadAnalysis]);

  // A plan with North but no zones yet (e.g. North set, then page closed) gets its zones computed here.
  const fp = project?.floor_plan;
  useEffect(() => {
    if (fp && fp.status === "north_set" && !fp.zones.length) api.calculateZones(fp.id).then(() => reload()).catch(setError);
  }, [fp, reload]);

  async function run() {
    if (!fp) return;
    setRunning(true); setError(null);
    try { setAnalysis(await api.runAnalysis(fp.id)); await reload(); }
    catch (e) { setError(e); }
    finally { setRunning(false); }
  }
  async function report() {
    setReporting(true); setError(null);
    try { await api.createReport(id); router.push(`/projects/${id}/report`); }
    catch (e) { setError(e); setReporting(false); }
  }

  if (loadError) return <ErrorNote error={loadError} onRetry={reload} />;
  if (!project || analysis === undefined) return <Loading />;
  const readyToRun = fp && ["north_set", "zoned", "analyzed"].includes(fp.status);
  const stale = analysis && project.floor_plan_status !== "analyzed";

  if (!analysis) {
    return (
      <div>
        <ProjectHeader project={project} current="analysis" title="Analysis" />
        {!readyToRun ? (
          <p className="text-slate">
            {fp?.verified ? <>Set North before running the analysis. <Link className="text-ink underline" href={`/projects/${id}/north`}>Set North</Link></>
              : <>Verify the floor plan first. <Link className="text-ink underline" href={`/projects/${id}/verify`}>Verify plan</Link></>}
          </p>
        ) : (
          <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
            <div className="panel p-4">
              <PlanCanvas imageUrl={fp!.image_url} width={fp!.width} height={fp!.height} zones={fp!.zones} centre={fp!.centre}
                northAngle={fp!.north?.north_angle ?? null}
                rooms={fp!.rooms.map((r) => ({ id: r.id, label: r.label, polygon: r.polygon, sublabel: r.primary_zone ?? undefined }))}
                openings={fp!.openings} />
            </div>
            <aside className="space-y-4">
              <div className="panel space-y-2 p-5 text-sm">
                <p className="font-medium">Ready to analyse</p>
                <p className="text-ink-soft">The centre (Brahmasthan) and 3 × 3 zone grid are calculated from your verified plan with North at {Math.round(fp!.north?.north_angle ?? 0)}°.</p>
                <p className="text-ink-soft">The analysis checks each room, the main entrance and each zone against the approved rules in the active Vastu rule set, then scores the results.</p>
              </div>
              <ErrorNote error={error} />
              <button className="btn-primary w-full" onClick={run} disabled={running}>{running && <Spinner />} Run Vastu analysis</button>
            </aside>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <ProjectHeader project={project} current="analysis" title="Analysis">
        <button className="btn-secondary" onClick={run} disabled={running || !readyToRun}>{running && <Spinner />} Re-run analysis</button>
        <Link className="btn-secondary" href={`/projects/${id}/insights`}>Insights</Link>
        <button className="btn-primary" onClick={report} disabled={reporting || !!stale}>{reporting && <Spinner />} Generate PDF report</button>
      </ProjectHeader>
      {stale && (
        <div className="rounded border border-warning/30 bg-warning-light p-3 text-sm">
          The plan or North direction changed after this analysis was run.{" "}
          {readyToRun ? <button className="text-ink underline" onClick={run}>Re-run the analysis</button>
            : <Link className="text-ink underline" href={`/projects/${id}/north`}>Confirm North</Link>} to bring the results up to date.
        </div>
      )}
      <ErrorNote error={error} />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_400px]">
        <PlanPanel a={analysis} selected={selected} onSelect={setSelected} />
        <div className="space-y-6">
          <ScorePanel a={analysis} />
          <div className="-mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm">
            <Link className="text-ink underline" href={`/projects/${id}/insights/explain`}>Explain the score</Link>
            <Link className="text-ink underline" href={`/projects/${id}/insights/passport`}>How reliable is this?</Link>
            <Link className="text-ink underline" href={`/projects/${id}/insights/fitcheck`}>Which remedies fit me?</Link>
          </div>
          <section className="panel" aria-labelledby="sum-h">
            <h2 id="sum-h" className="border-b border-hairline px-4 py-3 font-medium">Most important findings</h2>
            {analysis.summary.length ? (
              <ol className="divide-y divide-hairline text-sm">
                {analysis.summary.map((f) => (
                  <li key={f.id} className="flex gap-3 px-4 py-2.5">
                    <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${BUCKET_STYLE[f.bucket].dot}`} aria-label={BUCKET_STYLE[f.bucket].label} />
                    <span>{f.finding}</span>
                  </li>
                ))}
              </ol>
            ) : <p className="px-4 py-3 text-sm text-positive">No warnings or major issues under this rule set.</p>}
          </section>
          <p className="text-xs text-slate">
            Property: {project.property?.name ?? project.name} · analysed {new Date(analysis.created_at).toLocaleString()} · rule set {analysis.rule_set.name} (v{analysis.rule_set.version})
          </p>
        </div>
      </div>

      <RoomTable a={analysis} selected={selected} onSelect={setSelected} />
      <div className="grid gap-6 lg:grid-cols-2">
        <FindingsPanel a={analysis} />
        <RemediesPanel a={analysis} />
      </div>
      <p className="max-w-4xl text-xs leading-relaxed text-slate">{analysis.rule_set.disclaimer}</p>
    </div>
  );
}
