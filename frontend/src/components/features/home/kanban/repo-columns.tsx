/**
 * Container for a single repo's Kanban columns
 */

import type { SavedRepository } from "#/api/saved-repos-service/saved-repos.types";
import { useRepoIdeas } from "#/hooks/query/use-repo-ideas";
import { GitProviderIcon } from "#/components/shared/git-provider-icon";
import { Provider } from "#/types/settings";
import CodeBranchIcon from "#/icons/u-code-branch.svg?react";
import { IdeasColumn } from "./ideas-column";
import { BuildingColumn } from "./building-column";

interface RepoColumnsProps {
  repo: SavedRepository;
  onRemove?: () => void;
}

export function RepoColumns({ repo, onRemove }: RepoColumnsProps) {
  const { data: ideas = [], isLoading } = useRepoIdeas(repo.repo_full_name);

  // Split ideas into "ideas" (not building) and "building" (has conversation)
  const ideasOnly = ideas.filter((i) => !i.building_conversation_id);
  const buildingIdeas = ideas.filter((i) => i.building_conversation_id);

  const repoName = repo.repo_full_name.split("/").pop() || repo.repo_full_name;

  return (
    <div className="flex-shrink-0">
      {/* Repo Header */}
      <div className="flex items-center justify-between mb-4 px-1">
        <div className="flex items-center gap-3">
          <GitProviderIcon
            gitProvider={repo.git_provider as Provider}
            className="w-5 h-5"
          />
          <div>
            <h2
              className="text-white font-medium text-base truncate max-w-[300px]"
              title={repo.repo_full_name}
            >
              {repoName}
            </h2>
            <div className="flex items-center gap-1 text-xs text-[#A3A3A3]">
              <CodeBranchIcon width={12} height={12} />
              <span>{repo.branch}</span>
            </div>
          </div>
        </div>

        {/* Remove button */}
        {onRemove && (
          <button
            type="button"
            onClick={onRemove}
            className="text-[#6B7280] hover:text-red-400 transition-colors p-1"
            title="Remove repository"
            aria-label="Remove repository"
          >
            <svg
              width="16"
              height="16"
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

      {/* Columns */}
      <div className="flex gap-4">
        {isLoading ? (
          <>
            <div className="w-[280px] h-[300px] bg-[#1E1F22] rounded-xl animate-pulse" />
            <div className="w-[280px] h-[300px] bg-[#1E1F22] rounded-xl animate-pulse" />
          </>
        ) : (
          <>
            <IdeasColumn repoFullName={repo.repo_full_name} ideas={ideasOnly} />
            <BuildingColumn repo={repo} buildingIdeas={buildingIdeas} />
          </>
        )}
      </div>
    </div>
  );
}
