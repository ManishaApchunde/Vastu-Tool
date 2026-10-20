"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ErrorNote, Loading, Spinner } from "@/components/ui";
import { useProject } from "@/components/useProject";
import { ProjectHeader } from "@/features/ProjectHeader";
import { VerifyEditor, type EdOpening, type EdRoom } from "@/features/verify/Editor";
import { api } from "@/services/api";
import type { Detection, FloorPlan } from "@/types/api";

export default function VerifyPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { project, error: loadError, reload } = useProject(id);
  const [fp, setFp] = useState<FloorPlan | null>(null);
  const [detection, setDetection] = useState<Detection | null | undefined>(undefined);
  const [roomTypes, setRoomTypes] = useState<{ value: string; label: string }[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => { api.roomTypes().then(setRoomTypes).catch(setError); }, []);
  useEffect(() => { if (project?.floor_plan) setFp(project.floor_plan); }, [project]);

  // Wait for the AI job if it is still running, then load its suggestions.
  useEffect(() => {
    if (!fp) return;
    if (fp.status === "processing") {
      const t = setTimeout(() => api.floorPlan(fp.id).then(setFp).catch(setError), 1500);
      return () => clearTimeout(t);
    }
    if (detection !== undefined) return;
    if (!fp.has_detection) { setDetection(null); return; }
    api.detection(fp.id).then((d) => setDetection(d.detection)).catch((e) => { setError(e); setDetection(null); });
  }, [fp, detection]);

  async function confirm(rooms: EdRoom[], openings: EdOpening[]) {
    if (!fp) return;
    setBusy(true); setError(null);
    try {
      await api.verify(fp.id, {
        boundary: null,
        rooms: rooms.map((r) => ({ label: r.label.trim(), room_type: r.room_type, polygon: r.polygon, source: r.source, confidence: r.confidence })),
        openings: openings.map((o) => ({ kind: o.kind, position: o.position, is_main_entrance: o.is_main_entrance, source: o.source, confidence: o.confidence })),
      });
      router.push(`/projects/${id}/north`);
    } catch (e) {
      setError(e); setBusy(false);
    }
  }

  if (loadError) return <ErrorNote error={loadError} onRetry={reload} />;
  if (!project) return <Loading />;
  if (!project.floor_plan) return (
    <div><ProjectHeader project={project} current="verify" title="Verify plan" />
      <p className="text-slate">Upload a floor plan first. <Link className="text-ink underline" href={`/projects/${id}/upload`}>Go to upload</Link></p></div>
  );

  return (
    <div>
      <ProjectHeader project={project} current="verify" title="Verify plan" />
      {!roomTypes.length && <ErrorNote error={error} onRetry={() => api.roomTypes().then(setRoomTypes).catch(setError)} />}
      {fp?.status === "processing" || detection === undefined || !roomTypes.length ? (
        <div className="panel flex items-center gap-3 p-6 text-slate"><Spinner /> {fp?.status === "processing" ? "The AI is still reading your plan…" : "Loading plan"}</div>
      ) : fp && (
        <>
          {!fp.verified && detection && (
            <p className="mb-4 max-w-3xl text-sm text-ink-soft">
              Dashed amber outlines are the AI's suggestions. Check each room's name and type, fix boundaries, and mark the main entrance.
              Anything you touch turns green. Nothing is analysed until you confirm.
            </p>
          )}
          {!detection && !fp.verified && (
            <div className="mb-4 rounded border border-warning/30 bg-warning-light p-3 text-sm">
              No AI suggestions are available for this plan. Use “Draw room”, “Add door” and “Add window” to trace it yourself.
            </div>
          )}
          <VerifyEditor key={fp.id} fp={fp} detection={detection ?? null} roomTypes={roomTypes} onConfirm={confirm} busy={busy} error={error} />
        </>
      )}
    </div>
  );
}
