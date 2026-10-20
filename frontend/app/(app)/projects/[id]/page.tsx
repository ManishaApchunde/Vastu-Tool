"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { PlanCanvas } from "@/components/PlanCanvas";
import { ErrorNote, Loading, ProjectStepper, StatusBadge, progressOf, scoreTone } from "@/components/ui";
import { useProject } from "@/components/useProject";
import { nextHref } from "@/features/ProjectRow";
import { api } from "@/services/api";

const NEXT_LABEL: Record<string, string> = {
  none: "Upload floor plan", uploaded: "Check upload", processing: "View AI progress", detection_failed: "Fix detection",
  detected: "Verify the plan", verified: "Set North", north_set: "Run analysis", zoned: "Run analysis", analyzed: "View analysis",
};

export default function ProjectPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { project, error, reload } = useProject(id);
  const [deleting, setDeleting] = useState(false);

  if (error) return <ErrorNote error={error} onRetry={reload} />;
  if (!project) return <Loading />;
  const fp = project.floor_plan;
  const prop = project.property;

  async function remove() {
    if (!confirm(`Delete "${project!.name}" and its floor plan, analysis and reports? This can't be undone.`)) return;
    setDeleting(true);
    try { await api.deleteProject(id); router.replace("/projects"); } catch { setDeleting(false); }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Link href="/projects" className="text-sm text-slate hover:text-ink">Projects</Link>
          <div className="mt-1 flex items-center gap-3">
            <h1 className="page-title">{project.name}</h1>
            <StatusBadge status={project.floor_plan_status} />
          </div>
        </div>
        <div className="flex gap-2">
          <button className="btn-danger" onClick={remove} disabled={deleting}>Delete</button>
          <Link href={nextHref(project)} className="btn-primary">{NEXT_LABEL[project.floor_plan_status ?? "none"]}</Link>
        </div>
      </div>
      <ProjectStepper projectId={id} status={project.floor_plan_status} current={(["upload", "verify", "north", "analysis", "report"] as const)[progressOf(project.floor_plan_status)]} />
      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="panel p-4">
          {fp ? (
            <PlanCanvas imageUrl={fp.image_url} width={fp.width} height={fp.height}
              rooms={fp.verified ? fp.rooms.map((r) => ({ id: r.id, label: r.label, polygon: r.polygon, sublabel: r.primary_zone ?? undefined })) : []}
              zones={fp.zones} centre={fp.centre} northAngle={fp.north?.north_angle ?? null} />
          ) : (
            <div className="flex h-72 flex-col items-center justify-center text-slate">
              <p>No floor plan uploaded yet.</p>
              <Link href={`/projects/${id}/upload`} className="btn-primary mt-3">Upload floor plan</Link>
            </div>
          )}
        </div>
        <aside className="space-y-4">
          <div className="panel p-5">
            <p className="text-sm text-slate">Overall Vastu score</p>
            <p className={`font-display text-5xl ${scoreTone(project.overall_score)}`}>{project.overall_score ?? "—"}<span className="text-lg text-slate"> / 100</span></p>
            {project.overall_score == null && <p className="mt-1 text-sm text-slate">Available after analysis.</p>}
          </div>
          <dl className="panel divide-y divide-hairline text-sm">
            {[
              ["Customer", prop?.client_name],
              ["Property type", prop?.property_type?.replace("_", " ")],
              ["Address", prop?.address],
              ["Built-up area", prop?.built_up_area_sqft ? `${prop.built_up_area_sqft.toLocaleString()} sq ft` : null],
              ["Floor plan", fp?.original_filename],
              ["North", fp?.north ? `${Math.round(fp.north.north_angle)}° from image top` : null],
              ["Created", new Date(project.created_at).toLocaleDateString()],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between gap-4 px-4 py-2.5">
                <dt className="text-slate">{k}</dt><dd className="text-right">{v || "—"}</dd>
              </div>
            ))}
          </dl>
          {prop?.notes && <p className="panel p-4 text-sm text-ink-soft">{prop.notes}</p>}
        </aside>
      </div>
    </div>
  );
}
