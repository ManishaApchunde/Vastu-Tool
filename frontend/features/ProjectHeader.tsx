"use client";
import Link from "next/link";
import { ProjectStepper, StatusBadge } from "@/components/ui";
import type { Project } from "@/types/api";

export function ProjectHeader({ project, current, title, children }: {
  project: Project; current: "upload" | "verify" | "north" | "analysis" | "report" | "insights"; title: string; children?: React.ReactNode;
}) {
  return (
    <div className="mb-6 space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Link href={`/projects/${project.id}`} className="text-sm text-slate hover:text-ink">{project.name}</Link>
          <div className="mt-1 flex items-center gap-3">
            <h1 className="page-title">{title}</h1>
            <StatusBadge status={project.floor_plan_status} />
          </div>
        </div>
        {children && <div className="flex flex-wrap gap-2">{children}</div>}
      </div>
      <ProjectStepper projectId={project.id} status={project.floor_plan_status} current={current} />
    </div>
  );
}
