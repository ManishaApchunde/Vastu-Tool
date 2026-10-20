"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ErrorNote, Loading, Spinner } from "@/components/ui";
import { ProjectRow } from "@/features/ProjectRow";
import { api } from "@/services/api";
import type { Project } from "@/types/api";

export default function DashboardPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [demoBusy, setDemoBusy] = useState(false);

  const load = () => api.projects().then(setProjects).catch(setError);
  useEffect(() => { load(); }, []);

  async function openDemo() {
    setDemoBusy(true);
    try {
      const p = await api.createDemo();
      router.push(`/projects/${p.id}/analysis`);
    } catch (e) {
      setError(e);
      setDemoBusy(false);
    }
  }

  const analysed = projects?.filter((p) => p.overall_score != null).length ?? 0;
  const attention = projects?.filter((p) => p.floor_plan_status === "detection_failed" || p.floor_plan_status === "detected").length ?? 0;

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="mt-1 text-slate">Upload a floor plan, check what the AI found, set North, and get a rule-based Vastu assessment.</p>
        </div>
        <div className="flex gap-2">
          <button className="btn-secondary" onClick={openDemo} disabled={demoBusy}>{demoBusy && <Spinner />} Open demo project</button>
          <Link href="/projects/new" className="btn-primary">New project</Link>
        </div>
      </div>
      <ErrorNote error={error} onRetry={load} />
      {!projects && !error && <Loading />}
      {projects && (
        <>
          <dl className="grid grid-cols-3 divide-x divide-hairline panel">
            {[["Projects", projects.length], ["Analysed", analysed], ["Waiting on you", attention]].map(([k, v]) => (
              <div key={k} className="px-5 py-4">
                <dt className="text-sm text-slate">{k}</dt>
                <dd className="font-display text-3xl">{v}</dd>
              </div>
            ))}
          </dl>
          <section>
            <h2 className="mb-3 text-lg font-medium">Recent projects</h2>
            {projects.length === 0 ? (
              <div className="panel p-8 text-center">
                <p className="text-ink">No projects yet.</p>
                <p className="mt-1 text-sm text-slate">Start with your own floor plan, or open the demo to see a finished analysis.</p>
                <div className="mt-4 flex justify-center gap-2">
                  <Link href="/projects/new" className="btn-primary">Create a project</Link>
                  <button className="btn-secondary" onClick={openDemo} disabled={demoBusy}>Open demo project</button>
                </div>
              </div>
            ) : (
              <ul className="panel divide-y divide-hairline">
                {projects.slice(0, 6).map((p) => <ProjectRow key={p.id} project={p} />)}
              </ul>
            )}
          </section>
        </>
      )}
    </div>
  );
}
