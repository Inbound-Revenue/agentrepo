/**
 * RepoCard component - displays a saved repository with its pre-warmed status
 * and existing conversations
 */

import React from "react";
import { Link } from "react-router";
import CodeBranchIcon from "#/icons/u-code-branch.svg?react";
import { GitProviderIcon } from "#/components/shared/git-provider-icon";
import { Provider } from "#/types/settings";
import type { SavedRepository, PrewarmedConversation } from "#/api/saved-repos-service/saved-repos.types";
import type { Conversation } from "#/api/open-hands.types";
import { useClaimConversation } from "#/hooks/mutation/use-saved-repos-mutations";
import { formatTimeDelta } from "#/utils/format-time-delta";

interface RepoCardProps {
  repo: SavedRepository;
  conversations?: Conversation[];
  onRemove?: () => void;
}

const warmingStepLabels: Record<string, string> = {
  queued: "Queued",
  initializing: "Initializing",
  cloning_repo: "Cloning repo",
  building_runtime: "Building container",
  starting_agent: "Running autostart",
  creating_metadata: "Creating metadata",
  ready: "Ready",
  error: "Error",
};

export function RepoCard({ repo, conversations = [], onRemove }: RepoCardProps) {
  const claimConversation = useClaimConversation();
  const [isRemoving, setIsRemoving] = React.useState(false);

  const repoName = repo.repo_full_name.split("/").pop() || repo.repo_full_name;

  const handleClaimConversation = async () => {
    claimConversation.mutate(repo.repo_full_name);
  };

  const handleRemove = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (onRemove) {
      setIsRemoving(true);
      onRemove();
    }
  };

  // Filter conversations for this repo (exclude prewarmed ones)
  const repoConversations = conversations.filter(
    (conv) => conv.selected_repository === repo.repo_full_name
  );

  // Combine prewarmed conversations with recent ones for display
  const prewarmedConvIds = new Set(repo.prewarmed_conversations.map(c => c.conversation_id));

  return (
    <div className="flex flex-col gap-3 p-5 rounded-xl border border-[#727987] bg-[#26282D] min-w-[280px] max-w-[340px]">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <GitProviderIcon
              gitProvider={repo.git_provider as Provider}
              className="w-5 h-5"
            />
            <span
              className="text-white font-medium text-sm truncate max-w-[180px]"
              title={repo.repo_full_name}
            >
              {repoName}
            </span>
          </div>
          <div className="flex items-center gap-1 text-xs text-[#A3A3A3]">
            <CodeBranchIcon width={12} height={12} />
            <span>{repo.branch}</span>
          </div>
        </div>
        
        {/* Remove button */}
        <div className="flex items-center gap-2">
          {onRemove && (
            <button
              onClick={handleRemove}
              disabled={isRemoving}
              className="text-[#A3A3A3] hover:text-red-400 transition-colors p-1"
              title="Remove repository"
            >
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Conversations List - shows both prewarmed and recent */}
      {(repo.prewarmed_conversations.length > 0 || repoConversations.length > 0) && (
        <div className="flex flex-col gap-1">
          <span className="text-xs text-[#A3A3A3] font-medium">
            Conversations ({repo.prewarmed_conversations.length + repoConversations.length})
          </span>
          <div className="flex flex-col gap-1 max-h-[180px] overflow-y-auto custom-scrollbar">
            {/* Prewarmed conversations first - clickable if ready */}
            {repo.prewarmed_conversations.map((conv) => (
              <PrewarmedConversationRow 
                key={conv.conversation_id} 
                conv={conv} 
                onClaim={handleClaimConversation}
                isClaiming={claimConversation.isPending}
              />
            ))}
            {/* Then recent conversations (excluding any that are in prewarmed list) */}
            {repoConversations
              .filter(conv => !prewarmedConvIds.has(conv.conversation_id))
              .slice(0, 5)
              .map((conv) => (
              <Link
                key={conv.conversation_id}
                to={`/conversations/${conv.conversation_id}`}
                className="flex items-center justify-between p-2 rounded hover:bg-[#3D3F45] transition-colors text-xs"
              >
                <span className="text-white truncate max-w-[160px]">
                  {conv.title || `Conversation ${conv.conversation_id.slice(0, 5)}`}
                </span>
                {conv.created_at && (
                  <span className="text-[#A3A3A3]">
                    {formatTimeDelta(conv.created_at)}
                  </span>
                )}
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function PrewarmedConversationRow({ 
  conv, 
  onClaim,
  isClaiming 
}: { 
  conv: PrewarmedConversation;
  onClaim: () => void;
  isClaiming: boolean;
}) {
  const getStatusDisplay = () => {
    const step = conv.warming_step || conv.status;
    const label = warmingStepLabels[step] || step;
    
    switch (conv.status) {
      case 'ready':
        return { 
          bgColor: 'bg-green-500/20', 
          textColor: 'text-green-400', 
          label: 'Ready',
          icon: '✓',
          clickable: true
        };
      case 'warming':
        return { 
          bgColor: 'bg-yellow-500/20', 
          textColor: 'text-yellow-400', 
          label,
          icon: null,
          animate: true,
          clickable: false
        };
      case 'error':
        return { 
          bgColor: 'bg-red-500/20', 
          textColor: 'text-red-400', 
          label: conv.error_message || 'Error',
          icon: '✗',
          clickable: false
        };
      default:
        return { 
          bgColor: 'bg-gray-500/20', 
          textColor: 'text-gray-400', 
          label: 'Pending',
          icon: null,
          clickable: false
        };
    }
  };

  const { bgColor, textColor, label, icon, animate, clickable } = getStatusDisplay();

  const handleClick = () => {
    if (clickable && !isClaiming) {
      onClaim();
    }
  };

  return (
    <div 
      className={`flex items-center justify-between p-2 rounded bg-[#1E1F22] text-xs ${
        clickable ? 'cursor-pointer hover:bg-[#2A2B2F] transition-colors' : ''
      }`}
      onClick={handleClick}
      role={clickable ? 'button' : undefined}
    >
      <span className="text-white truncate max-w-[120px]">
        Conversation {conv.conversation_id.slice(0, 5)}
      </span>
      <span 
        className={`flex items-center gap-1 px-2 py-0.5 rounded ${bgColor} ${textColor} text-[10px] font-medium`}
        title={conv.error_message || undefined}
      >
        {animate && (
          <span className="inline-block w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
        )}
        {icon && <span>{icon}</span>}
        {isClaiming && clickable ? 'Opening...' : label}
      </span>
    </div>
  );
}
