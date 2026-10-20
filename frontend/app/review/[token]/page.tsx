"use client";
import { useParams } from "next/navigation";
import { ReviewPackView } from "@/features/insights/ReviewPackView";

/** Public, read-only review page for an invited Vastu consultant or architect (no account needed). */
export default function PublicReviewPage() {
  const { token } = useParams<{ token: string }>();
  return <ReviewPackView token={token} />;
}
