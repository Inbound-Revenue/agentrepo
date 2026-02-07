/**
 * "Building" column in the Kanban board
 */

import { useDroppable } from "@dnd-kit/core";
import type { SavedRepository } from "#/api/saved-repos-service/saved-repos.types";
import type { RepoIdea } from "#/api/repo-ideas-service";
import { BuildingCard } from "./building-card";
import { PoolStatusBadge } from "./pool-status-badge";

interface BuildingColumnProps {
  repo: SavedRepository;
  buildingIdeas: RepoIdea[];
}

export function BuildingColumn({ repo, buildingIdeas }: BuildingColumnProps) {
  const { setNodeRef, isOver } = useDroppable({
    id: `building-${repo.repo_full_name}`,
  });

  return (
    <div
      ref={setNodeRef}
      className={`w-[280px] bg-[#1E1F22] rounded-xl p-4 flex flex-col transition-colors ${
        isOver ? "bg-[#252629] ring-2 ring-blue-500/50" : ""
      }`}
    >
      <div className="flex items-center justify-between mb-4">
        {/* eslint-disable-next-line i18next/no-literal-string */}
        <h3 className="text-white font-medium text-sm">Building</h3>
        <PoolStatusBadge repo={repo} />
      </div>

      {/* Droppable area */}
      <div className="flex flex-col gap-2 flex-1 overflow-y-auto custom-scrollbar max-h-[calc(100vh-320px)] min-h-[100px]">
        {buildingIdeas.length === 0 ? (
          <div className={`flex-1 flex items-center justify-center text-[#6B7280] text-sm border-2 border-dashed rounded-lg p-4 transition-colors ${
            isOver ? "border-blue-500/50 bg-blue-500/10" : "border-[#3D3F45]"
          }`}>
            {isOver ? "Drop to start building" : "Drag ideas here to build"}
          </div>
        ) : (
          buildingIdeas.map((idea) => (
            <BuildingCard
              key={idea.id}
              idea={idea}
              repoFullName={repo.repo_full_name}
            />
          ))
        )}
      </div>
    </div>
  );
}
