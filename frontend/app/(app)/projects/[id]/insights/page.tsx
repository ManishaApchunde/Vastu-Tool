"use client";
import { useParams } from "next/navigation";
import { InsightsOverview } from "@/features/insights/Overview";

export default function InsightsPage() {
  const { id } = useParams<{ id: string }>();
  return <InsightsOverview projectId={id} />;
}
