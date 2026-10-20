"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ALL_LAYERS, PlanCanvas } from "@/components/PlanCanvas";
import { ErrorNote, Loading, Spinner } from "@/components/ui";
import { useProject } from "@/components/useProject";
import { CompassDial } from "@/features/north/CompassDial";
import { ProjectHeader } from "@/features/ProjectHeader";
import { api } from "@/services/api";

const PRESETS = [[0, "Top"], [90, "Right"], [180, "Bottom"], [270, "Left"]] as const;
const norm = (a: number) => ((Math.round(a) % 360) + 360) % 360;
const compass = (a: number) => ["up", "upper right", "right", "lower right", "down", "lower left", "left", "upper left"][Math.round(a / 45) % 8];

export default function NorthPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { project, error: loadError, reload } = useProject(id);
  const [angle, setAngle] = useState<number | null>(null);
  const [touched, setTouched] = useState(false);
  const [northUp, setNorthUp] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const fp = project?.floor_plan;
  useEffect(() => { if (fp && angle == null) setAngle(fp.north ? norm(fp.north.north_angle) : 0); }, [fp, angle]);

  if (loadError) return <ErrorNote error={loadError} onRetry={reload} />;
  if (!project || angle == null) return <Loading />;
  if (!fp?.verified) return (
    <div><ProjectHeader project={project} current="north" title="Set North" />
      <p className="text-slate">Verify the floor plan before setting North. <Link className="text-ink underline" href={`/projects/${id}/verify`}>Go to verification</Link></p></div>
  );
  const set = (a: number) => { setAngle(norm(a)); setTouched(true); };
  const alreadyConfirmed = fp.north?.confirmed && norm(fp.north.north_angle) === angle;

  async function confirm() {
    setBusy(true); setError(null);
    try {
      await api.setNorth(fp!.id, angle!);
      await api.calculateZones(fp!.id);
      router.push(`/projects/${id}/analysis`);
    } catch (e) { setError(e); setBusy(false); }
  }

  return (
    <div>
      <ProjectHeader project={project} current="north" title="Set North" />
      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
        <div className="space-y-2">
          <div className="panel p-4">
            <PlanCanvas imageUrl={fp.image_url} width={fp.width} height={fp.height} northAngle={angle} northUp={northUp}
              rooms={fp.rooms.map((r) => ({ id: r.id, label: r.label, polygon: r.polygon }))}
              openings={fp.openings} layers={{ ...ALL_LAYERS, zones: false, centre: false }} />
          </div>
          <label className="flex items-center gap-2 text-sm text-slate">
            <input type="checkbox" checked={northUp} onChange={(e) => setNorthUp(e.target.checked)} /> Rotate preview so North points up
          </label>
        </div>
        <aside className="space-y-4">
          <div className="panel space-y-4 p-5">
            <p className="text-sm text-ink-soft">
              Where is true North on this drawing? Don't assume it's the top of the page: use the plan's north arrow, the site plan, or a compass reading from the property.
            </p>
            <CompassDial angle={angle} onChange={set} />
            <div className="flex items-center justify-center gap-1">
              <button className="btn-secondary px-2.5" onClick={() => set(angle - 15)} aria-label="Rotate 15 degrees anticlockwise">−15</button>
              <button className="btn-secondary px-2.5" onClick={() => set(angle - 1)} aria-label="Rotate 1 degree anticlockwise">−1</button>
              <input className="field w-20 text-center" type="number" min={0} max={359} value={angle} aria-label="North angle in degrees"
                onChange={(e) => set(Number(e.target.value) || 0)} />
              <button className="btn-secondary px-2.5" onClick={() => set(angle + 1)} aria-label="Rotate 1 degree clockwise">+1</button>
              <button className="btn-secondary px-2.5" onClick={() => set(angle + 15)} aria-label="Rotate 15 degrees clockwise">+15</button>
            </div>
            <div>
              <p className="mb-1.5 text-xs text-slate">North is towards the image's…</p>
              <div className="grid grid-cols-4 gap-1">
                {PRESETS.map(([a, l]) => (
                  <button key={a} onClick={() => set(a)} className={angle === a ? "btn-primary px-2" : "btn-secondary px-2"}>{l}</button>
                ))}
              </div>
            </div>
            <p className="text-sm">North points <strong className="font-medium">{compass(angle)}</strong> on the drawing, {angle}° clockwise from the top edge.</p>
          </div>
          {!fp.north && !touched && (
            <p className="rounded border border-warning/30 bg-warning-light p-3 text-sm">North hasn't been set. The dial starts at the top edge only as a starting point.</p>
          )}
          <ErrorNote error={error} />
          <button className="btn-primary w-full" disabled={busy} onClick={confirm}>
            {busy && <Spinner />} {alreadyConfirmed ? "Keep North and continue" : `Confirm North at ${angle}°`}
          </button>
          <p className="text-xs text-slate">Confirming calculates the centre (Brahmasthan) and the 3 × 3 zone grid for this orientation.</p>
        </aside>
      </div>
    </div>
  );
}
