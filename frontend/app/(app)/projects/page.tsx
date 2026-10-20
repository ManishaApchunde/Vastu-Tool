"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ErrorNote, Loading } from "@/components/ui";
import { ProjectRow } from "@/features/ProjectRow";
import { api } from "@/services/api";
import type { Project } from "@/types/api";

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [q, setQ] = useState("");
  const load = () => api.projects().then(setProjects).catch(setError);
  useEffect(() => { load(); }, []);
  const shown = projects?.filter((p) => `${p.name} ${p.property?.address ?? ""}`.toLowerCase().includes(q.toLowerCase()));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="page-title">Projects</h1>
        <Link href="/projects/new" className="btn-primary">New project</Link>
      </div>
      <input className="field max-w-sm" placeholder="Search by name or address" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search projects" />
      <ErrorNote error={error} onRetry={load} />
      {!projects && !error && <Loading />}
      {shown && (shown.length ? (
        <ul className="panel divide-y divide-hairline">{shown.map((p) => <ProjectRow key={p.id} project={p} />)}</ul>
      ) : <p className="text-slate">{projects!.length ? "No projects match that search." : "No projects yet."}</p>)}
    </div>
  );
}
