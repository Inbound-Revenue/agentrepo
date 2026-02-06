/**
 * Status indicator for the RepoCard showing pre-warm status
 */

import type { PrewarmedConversation } from "#/api/saved-repos-service/saved-repos.types";

interface RepoCardStatusIndicatorProps {
  readyCount: number;
  warmingCount: number;
  poolSize: number;
  prewarmedConversations?: PrewarmedConversation[];
}

const warmingStepLabels: Record<string, string> = {
  queued: "Queued",
  initializing: "Initializing...",
  creating_metadata: "Setting up...",
  ready: "Ready",
  error: "Error",
};

export function RepoCardStatusIndicator({
  readyCount,
  warmingCount,
  poolSize,
  prewarmedConversations = [],
}: RepoCardStatusIndicatorProps) {
  const isReady = readyCount > 0;
  const isWarming = warmingCount > 0;

  let statusColor = "bg-gray-500";
  let statusText = "Pending";
  let pulseClass = "";

  if (isReady) {
    statusColor = "bg-green-500";
    statusText = `${readyCount}/${poolSize} Ready`;
  } else if (isWarming) {
    statusColor = "bg-yellow-500";
    // Get the current step from the first warming conversation
    const warmingConv = prewarmedConversations.find(c => c.status === 'warming');
    const stepLabel = warmingConv?.warming_step 
      ? warmingStepLabels[warmingConv.warming_step] || warmingConv.warming_step
      : "Warming";
    statusText = stepLabel;
    pulseClass = "animate-pulse";
  }

  return (
    <div className="flex items-center gap-1.5">
      <div
        className={`w-2 h-2 rounded-full ${statusColor} ${pulseClass}`}
        title={statusText}
      />
      <span className="text-[10px] text-[#A3A3A3]">{statusText}</span>
    </div>
  );
}
