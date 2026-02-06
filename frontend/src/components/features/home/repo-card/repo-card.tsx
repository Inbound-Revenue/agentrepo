/**
 * RepoCard component - displays a saved repository with its pre-warmed status
 * and existing conversations
 */

import React from "react";
import { Link } from "react-router";
import CodeBranchIcon from "#/icons/u-code-branch.svg?react";
import { GitProviderIcon } from "#/components/shared/git-provider-icon";
import { Provider } from "#/types/settings";
import type { SavedRepository } from "#/api/saved-repos-service/saved-repos.types";
import type { Conversation } from "#/api/open-hands.types";
import { useClaimConversation } from "#/hooks/mutation/use-saved-repos-mutations";
import { formatTimeDelta } from "#/utils/format-time-delta";
import { RepoCardStatusIndicator } from "./repo-card-status-indicator";

interface RepoCardProps {
  repo: SavedRepository;
  conversations?: Conversation[];
  onRemove?: () => void;
}

export function RepoCard({ repo, conversations = [], onRemove }: RepoCardProps) {
  const claimConversation = useClaimConversation();
  const [isRemoving, setIsRemoving] = React.useState(false);

  const repoName = repo.repo_full_name.split("/").pop() || repo.repo_full_name;
  const hasReadyConversation = repo.ready_count > 0;
  const isWarming = repo.warming_count > 0 && repo.ready_count === 0;

  const handleNewConversation = async () => {
    if (!hasReadyConversation) {
      // No ready conversation - could show a message or fallback to normal flow
      console.log("No ready conversations available, please wait...");
      return;
    }
    claimConversation.mutate(repo.repo_full_name);
  };

  const handleRemove = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (onRemove) {
      setIsRemoving(true);
      onRemove();
    }
  };

  // Filter conversations for this repo
  const repoConversations = conversations.filter(
    (conv) => conv.selected_repository === repo.repo_full_name
  );

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
        
        {/* Status + Remove */}
        <div className="flex items-center gap-2">
          <RepoCardStatusIndicator
            readyCount={repo.ready_count}
            warmingCount={repo.warming_count}
            poolSize={repo.pool_size}
          />
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

      {/* New Conversation Button */}
      <button
        onClick={handleNewConversation}
        disabled={!hasReadyConversation || claimConversation.isPending}
        className={`w-full py-2 px-4 rounded-lg font-medium text-sm transition-all ${
          hasReadyConversation
            ? "bg-[#4D6DFF] hover:bg-[#5C7CFF] text-white cursor-pointer"
            : isWarming
              ? "bg-[#3D3F45] text-[#A3A3A3] cursor-wait"
              : "bg-[#3D3F45] text-[#A3A3A3] cursor-not-allowed"
        }`}
      >
        {claimConversation.isPending
          ? "Opening..."
          : isWarming
            ? "Warming up..."
            : hasReadyConversation
              ? "New Conversation"
              : "Not Ready"}
      </button>

      {/* Existing Conversations */}
      {repoConversations.length > 0 && (
        <div className="flex flex-col gap-1 mt-1">
          <span className="text-xs text-[#A3A3A3] font-medium">
            Recent ({repoConversations.length})
          </span>
          <div className="flex flex-col gap-1 max-h-[120px] overflow-y-auto custom-scrollbar">
            {repoConversations.slice(0, 5).map((conv) => (
              <Link
                key={conv.conversation_id}
                to={`/conversations/${conv.conversation_id}`}
                className="flex items-center justify-between p-2 rounded hover:bg-[#3D3F45] transition-colors text-xs"
              >
                <span className="text-white truncate max-w-[160px]">
                  {conv.title || "Untitled"}
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

      {/* Pool info (subtle) */}
      <div className="text-[10px] text-[#6B7280] mt-auto">
        Pool: {repo.ready_count} ready, {repo.warming_count} warming
      </div>
    </div>
  );
}
