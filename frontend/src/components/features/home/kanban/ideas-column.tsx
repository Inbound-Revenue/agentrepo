/**
 * "Ideas & Issues" column in the Kanban board
 */

import {
  SortableContext,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { useDroppable } from "@dnd-kit/core";
import type { RepoIdea } from "#/api/repo-ideas-service";
import { IdeaCard } from "./idea-card";
import { AddIdeaInput } from "./add-idea-input";

interface IdeasColumnProps {
  repoFullName: string;
  ideas: RepoIdea[];
}

export function IdeasColumn({ repoFullName, ideas }: IdeasColumnProps) {
  const { setNodeRef, isOver } = useDroppable({
    id: `ideas-${repoFullName}`,
  });

  return (
    <div
      ref={setNodeRef}
      className={`w-[280px] bg-[#1E1F22] rounded-xl p-4 flex flex-col transition-colors ${
        isOver ? "bg-[#252629]" : ""
      }`}
    >
      {/* eslint-disable-next-line i18next/no-literal-string */}
      <h3 className="text-white font-medium mb-4 text-sm">Ideas & Issues</h3>

      <SortableContext
        id={`ideas-${repoFullName}`}
        items={ideas.map((i) => i.id)}
        strategy={verticalListSortingStrategy}
      >
        <div className="flex flex-col gap-2 flex-1 overflow-y-auto custom-scrollbar max-h-[calc(100vh-320px)]">
          {ideas.map((idea) => (
            <IdeaCard
              key={idea.id}
              idea={idea}
              repoFullName={repoFullName}
            />
          ))}
        </div>
      </SortableContext>

      {/* Always show input at bottom */}
      <AddIdeaInput repoFullName={repoFullName} />
    </div>
  );
}
