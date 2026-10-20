"use client";
import { useParams } from "next/navigation";
import { ToolPage } from "@/features/insights/ToolPage";

export default function InsightToolPage() {
  const { id, tool } = useParams<{ id: string; tool: string }>();
  return <ToolPage projectId={id} tool={tool} />;
}
