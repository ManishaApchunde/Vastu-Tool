"use client";
import { ChangeHistory } from "./ChangeHistory";
import { ConstructionStage } from "./ConstructionStage";
import { DailyLife } from "./DailyLife";
import { ExpertReview } from "./ExpertReview";
import { ExplainScore } from "./ExplainScore";
import { FamilyPriority } from "./FamilyPriority";
import { FitCheck } from "./FitCheck";
import { PostMove } from "./PostMove";
import type { ToolSlug } from "./shared";
import { TrustPassport } from "./TrustPassport";
import { VoiceExplainer } from "./VoiceExplainer";

const TOOLS: Record<ToolSlug, (p: { projectId: string }) => React.ReactNode> = {
  explain: ExplainScore, passport: TrustPassport, history: ChangeHistory, fitcheck: FitCheck, conflicts: DailyLife,
  family: FamilyPriority, stage: ConstructionStage, "post-move": PostMove, "expert-review": ExpertReview, voice: VoiceExplainer,
};

export function ToolPage({ projectId, tool }: { projectId: string; tool: string }) {
  const C = TOOLS[tool as ToolSlug];
  if (!C) return <p className="text-slate">Unknown tool.</p>;
  return <C projectId={projectId} />;
}
