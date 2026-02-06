/**
 * Status indicator for the RepoCard showing pre-warm status
 */

interface RepoCardStatusIndicatorProps {
  readyCount: number;
  warmingCount: number;
  poolSize: number;
}

export function RepoCardStatusIndicator({
  readyCount,
  warmingCount,
  poolSize,
}: RepoCardStatusIndicatorProps) {
  const isReady = readyCount > 0;
  const isWarming = warmingCount > 0 && readyCount === 0;
  const isEmpty = readyCount === 0 && warmingCount === 0;

  let statusColor = "bg-gray-500";
  let statusText = "Empty";
  let pulseClass = "";

  if (isReady) {
    statusColor = "bg-green-500";
    statusText = `${readyCount}/${poolSize} Ready`;
  } else if (isWarming) {
    statusColor = "bg-yellow-500";
    statusText = "Warming";
    pulseClass = "animate-pulse";
  } else if (isEmpty) {
    statusColor = "bg-gray-500";
    statusText = "Pending";
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
