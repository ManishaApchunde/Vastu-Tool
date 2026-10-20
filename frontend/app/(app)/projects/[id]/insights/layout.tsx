"use client";
import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { ErrorNote, Loading } from "@/components/ui";
import { useProject } from "@/components/useProject";
import { ProjectHeader } from "@/features/ProjectHeader";
import { TOOL_GROUPS } from "@/features/insights/shared";

export default function InsightsLayout({ children }: { children: React.ReactNode }) {
  const { id } = useParams<{ id: string }>();
  const path = usePathname();
  const { project, error, reload } = useProject(id);
  if (error) return <ErrorNote error={error} onRetry={reload} />;
  if (!project) return <Loading />;
  const base = `/projects/${id}/insights`;
  const link = (href: string, label: React.ReactNode, active: boolean) => (
    <Link href={href} aria-current={active ? "page" : undefined}
      className={`block rounded px-3 py-1.5 text-sm ${active ? "bg-white font-medium text-ink shadow-[inset_2px_0_0_#16283A]" : "text-ink-soft hover:bg-white/70 hover:text-ink"}`}>{label}</Link>
  );
  return (
    <div>
      <ProjectHeader project={project} current="insights" title="Insights">
        <Link className="btn-secondary" href={`/projects/${id}/analysis`}>Back to analysis</Link>
      </ProjectHeader>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[220px_minmax(0,1fr)]">
        <nav aria-label="Insight tools" className="min-w-0 lg:sticky lg:top-4 lg:self-start">
          <div className="flex gap-1 overflow-x-auto pb-2 lg:block lg:space-y-0.5 lg:overflow-visible lg:pb-0">
            {link(base, "Overview", path === base)}
            {TOOL_GROUPS.map((g) => (
              <div key={g.title} className="contents lg:block">
                <p className="hidden px-3 pb-1 pt-4 text-xs uppercase tracking-wide text-slate lg:block">{g.title}</p>
                {g.tools.map((t) => <div key={t.slug} className="shrink-0">{link(`${base}/${t.slug}`, t.label, path === `${base}/${t.slug}`)}</div>)}
              </div>
            ))}
          </div>
        </nav>
        <div className="min-w-0">{children}</div>
      </div>
    </div>
  );
}
