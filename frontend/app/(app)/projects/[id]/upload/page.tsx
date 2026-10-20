"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { ErrorNote, Loading, Spinner } from "@/components/ui";
import { useProject } from "@/components/useProject";
import { ProjectHeader } from "@/features/ProjectHeader";
import { api, ApiError } from "@/services/api";
import type { Detection, FloorPlan } from "@/types/api";

const ACCEPT = ["image/jpeg", "image/png", "application/pdf"];
const MAX_MB = 15;

export default function UploadPage() {
  const { id } = useParams<{ id: string }>();
  const { project, error: loadError, reload } = useProject(id);
  const [fp, setFp] = useState<FloorPlan | null>(null);
  const [detection, setDetection] = useState<Detection | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [replace, setReplace] = useState(false);
  const [drag, setDrag] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => { if (project?.floor_plan) setFp(project.floor_plan); }, [project]);

  // Poll while the AI job runs.
  const poll = useCallback(async (fpId: string) => {
    const next = await api.floorPlan(fpId);
    setFp(next);
    return next;
  }, []);
  useEffect(() => {
    if (!fp || (fp.status !== "processing" && fp.status !== "uploaded")) return;
    if (fp.status === "uploaded" && !fp.detection_job) return;
    const t = setInterval(() => poll(fp.id).catch(setError), 1500);
    return () => clearInterval(t);
  }, [fp, poll]);
  useEffect(() => {
    if (fp?.has_detection) api.detection(fp.id).then((d) => setDetection(d.detection)).catch(() => {});
  }, [fp?.id, fp?.has_detection]);
  useEffect(() => { if (fp && fp.status !== "processing") reload(); }, [fp?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  async function upload(file: File) {
    setError(null);
    if (!ACCEPT.includes(file.type) && !/\.(jpe?g|png|pdf)$/i.test(file.name)) {
      setError(new ApiError(415, "unsupported_type", "That file type isn't supported.", "Upload a JPG, PNG or PDF floor plan."));
      return;
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      setError(new ApiError(413, "too_large", `That file is larger than ${MAX_MB} MB.`, "Export the plan at a lower resolution or compress the PDF."));
      return;
    }
    setProgress(0);
    try {
      const next = await api.uploadFloorPlan(id, file, setProgress);
      setFp(next); setDetection(null); setReplace(false);
    } catch (e) {
      setError(e);
    } finally {
      setProgress(null);
    }
  }

  async function retry() {
    if (!fp?.detection_job) return;
    setError(null);
    try { await api.retryJob(fp.detection_job.id); await poll(fp.id); } catch (e) { setError(e); }
  }
  async function reanalyze() {
    if (!fp) return;
    try { await api.analyze(fp.id); await poll(fp.id); } catch (e) { setError(e); }
  }

  if (loadError) return <ErrorNote error={loadError} onRetry={reload} />;
  if (!project) return <Loading />;
  const showDrop = !fp || replace;
  const job = fp?.detection_job;

  return (
    <div>
      <ProjectHeader project={project} current="upload" title="Upload floor plan" />
      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
        <div className="panel p-4">
          {showDrop ? (
            <div
              onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
              onDrop={(e) => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files[0]; if (f) upload(f); }}
              className={`flex h-80 flex-col items-center justify-center rounded border-2 border-dashed text-center ${drag ? "border-ink bg-paper" : "border-hairline"}`}>
              {progress != null ? (
                <div className="w-64">
                  <p className="mb-2 text-sm text-ink">Uploading… {progress}%</p>
                  <div className="h-1.5 rounded bg-paper"><div className="h-1.5 rounded bg-ink transition-all" style={{ width: `${progress}%` }} /></div>
                </div>
              ) : (
                <>
                  <p className="text-ink">Drop a floor plan here</p>
                  <p className="mt-1 text-sm text-slate">JPG, PNG or PDF (first page), up to {MAX_MB} MB. A clear, straight-on scan works best.</p>
                  <button className="btn-primary mt-4" onClick={() => input.current?.click()}>Choose file</button>
                  {replace && <button className="btn-quiet mt-2" onClick={() => setReplace(false)}>Keep current plan</button>}
                </>
              )}
              <input ref={input} type="file" accept=".jpg,.jpeg,.png,.pdf" className="hidden"
                onChange={(e) => { const f = e.target.files?.[0]; if (f) upload(f); e.target.value = ""; }} />
            </div>
          ) : fp && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={fp.image_url} alt={`Preview of ${fp.original_filename}`} className="mx-auto max-h-[70vh] w-auto" />
          )}
        </div>

        <aside className="space-y-4">
          <ErrorNote error={error} />
          {fp && (
            <div className="panel divide-y divide-hairline text-sm">
              <Row k="File" v={fp.original_filename} />
              <Row k="Upload" v={<span className="text-positive">Complete</span>} />
              <Row k="Image size" v={`${fp.width} × ${fp.height} px`} />
              <Row k="AI analysis" v={
                fp.status === "processing" || (job && (job.status === "queued" || job.status === "running"))
                  ? <span className="flex items-center gap-2 text-brass"><Spinner /> Detecting rooms and openings</span>
                  : fp.status === "detection_failed" ? <span className="text-major">Failed</span>
                  : fp.has_detection ? <span className="text-positive">Complete ({fp.detection_provider})</span>
                  : <span className="text-slate">Not started</span>} />
            </div>
          )}

          {fp?.quality?.warnings?.length ? (
            <div className="rounded border border-warning/30 bg-warning-light p-4 text-sm">
              <p className="font-medium text-warning">Image quality</p>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-ink-soft">{fp.quality.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
            </div>
          ) : null}

          {fp?.status === "detection_failed" && (
            <div className="rounded border border-major/30 bg-major-light p-4 text-sm">
              <p className="font-medium text-major">The AI couldn't read this plan.</p>
              <p className="mt-1 text-ink-soft">{job?.error ?? "Detection failed."} {job && `Attempt ${job.attempts} of ${job.max_attempts}.`}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {job?.can_retry && <button className="btn-secondary" onClick={retry}>Retry detection</button>}
                <Link href={`/projects/${id}/verify`} className="btn-secondary">Draw rooms manually</Link>
                <button className="btn-quiet" onClick={() => setReplace(true)}>Upload a clearer file</button>
              </div>
            </div>
          )}

          {detection && fp && fp.status !== "processing" && fp.status !== "detection_failed" && (
            <div className="panel p-4 text-sm">
              <p className="font-medium">AI detected</p>
              <p className="mt-1 text-slate">
                {detection.rooms.length} rooms, {detection.doors.length} doors, {detection.windows.length} windows
                {detection.stairs.length ? `, ${detection.stairs.length} staircase` : ""}. These are suggestions until you verify them.
              </p>
              {detection.warnings.length > 0 && (
                <ul className="mt-2 list-disc pl-5 text-warning">{detection.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
              )}
              <Link href={`/projects/${id}/verify`} className="btn-primary mt-4 w-full">
                {fp.verified ? "Review verified plan" : "Review detected plan"}
              </Link>
            </div>
          )}

          {fp && !showDrop && (
            <div className="flex flex-wrap gap-2">
              <button className="btn-quiet" onClick={() => setReplace(true)}>Replace file</button>
              {fp.status !== "processing" && <button className="btn-quiet" onClick={reanalyze}>Run AI detection again</button>}
            </div>
          )}
          {fp && !showDrop && fp.verified && (
            <p className="text-xs text-slate">Replacing the file or re-running detection means you'll need to verify the plan and set North again.</p>
          )}
        </aside>
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return <div className="flex justify-between gap-4 px-4 py-2.5"><span className="text-slate">{k}</span><span className="text-right">{v}</span></div>;
}
