"use client";
import Link from "next/link";
import { StatusBadge, progressOf, scoreTone } from "@/components/ui";
import type { Project } from "@/types/api";

const NEXT_STEP = ["upload", "verify", "north", "analysis", "analysis"];

export function nextHref(p: Project) {
  const s = p.floor_plan_status;
  if (s === "processing" || s === "uploaded" || s === "detection_failed") return `/projects/${p.id}/upload`;
  return `/projects/${p.id}/${NEXT_STEP[progressOf(s)]}`;
}

export function ProjectRow({ project: p }: { project: Project }) {
  return (
    <li>
      <Link href={`/projects/${p.id}`} className="flex items-center gap-4 px-5 py-3.5 hover:bg-paper/60">
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium text-ink">{p.name} {p.is_demo && <span className="ml-1 text-xs font-normal text-slate">Demo</span>}</p>
          <p className="truncate text-sm text-slate">{p.property?.address || p.property?.property_type?.replace("_", " ") || "—"}</p>
        </div>
        <StatusBadge status={p.floor_plan_status} />
        <span className={`w-12 text-right font-display text-xl ${scoreTone(p.overall_score)}`}>{p.overall_score ?? "—"}</span>
      </Link>
    </li>
  );
}
