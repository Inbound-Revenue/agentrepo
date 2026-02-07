/**
 * Main Kanban board component
 */

import React from "react";
import {
  DndContext,
  DragOverlay,
  closestCorners,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { sortableKeyboardCoordinates } from "@dnd-kit/sortable";
import { useSavedRepos } from "#/hooks/query/use-saved-repos";
import { useRepoIdeas } from "#/hooks/query/use-repo-ideas";
import { useBuildIdea } from "#/hooks/mutation/use-repo-ideas-mutations";
import { RepoColumns } from "./repo-columns";
import { AddRepoCard } from "#/components/features/home/repo-card";
import { useRemoveSavedRepo } from "#/hooks/mutation/use-saved-repos-mutations";

interface KanbanBoardProps {
  onAddRepo: () => void;
}

interface BuildIdeaEvent extends CustomEvent {
  detail: { repoFullName: string; ideaId: string };
}

/**
 * Wrapper component to handle build mutations per repo
 */
function BuildIdeaMutationWrapper({ repoFullName }: { repoFullName: string }) {
  const buildIdea = useBuildIdea(repoFullName);

  React.useEffect(() => {
    const handleBuildIdeaEvent = (event: Event) => {
      const customEvent = event as BuildIdeaEvent;
      if (customEvent.detail.repoFullName === repoFullName) {
        buildIdea.mutate(customEvent.detail.ideaId);
      }
    };

    window.addEventListener("build-idea", handleBuildIdeaEvent);
    return () => {
      window.removeEventListener("build-idea", handleBuildIdeaEvent);
    };
  }, [repoFullName, buildIdea]);

  return null;
}

/**
 * Content for the drag overlay
 */
function DragOverlayContent({
  activeId,
  repoFullName,
}: {
  activeId: string;
  repoFullName: string;
}) {
  const { data: ideas = [] } = useRepoIdeas(repoFullName);
  const idea = ideas.find((i) => i.id === activeId);

  if (!idea) return null;

  return (
    <div className="bg-[#26282D] rounded-lg p-3 shadow-xl opacity-90 w-[260px]">
      <p className="text-white text-sm break-words whitespace-pre-wrap">
        {idea.text}
      </p>
    </div>
  );
}

export function KanbanBoard({ onAddRepo }: KanbanBoardProps) {
  const { data: savedRepos = [], isLoading: isLoadingRepos } = useSavedRepos();
  const removeSavedRepo = useRemoveSavedRepo();
  const [activeId, setActiveId] = React.useState<string | null>(null);
  const [activeRepoName, setActiveRepoName] = React.useState<string | null>(null);

  // Set up sensors for drag detection
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8, // 8px movement required before drag starts
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  );

  const handleBuildIdea = React.useCallback((repoFullName: string, ideaId: string) => {
    // We need to call the build mutation
    // This is handled via the BuildIdeaMutationWrapper below
    const event = new CustomEvent("build-idea", {
      detail: { repoFullName, ideaId },
    });
    window.dispatchEvent(event);
  }, []);

  const handleDragStart = React.useCallback((event: DragStartEvent) => {
    const { active } = event;
    setActiveId(active.id as string);

    // Find which repo this idea belongs to
    // For now, set the first repo - the overlay will find the correct one
    if (savedRepos.length > 0) {
      setActiveRepoName(savedRepos[0].repo_full_name);
    }
  }, [savedRepos]);

  const handleDragEnd = React.useCallback((event: DragEndEvent) => {
    const { active, over } = event;

    setActiveId(null);
    setActiveRepoName(null);

    if (!over) return;

    const activeIdStr = active.id as string;
    const overIdStr = over.id as string;

    // Check if dropped on a "Building" column
    if (overIdStr.startsWith("building-")) {
      // Find the idea's original repo (it might be different from drop target)
      // For now, we only support dragging within the same repo
      for (const repo of savedRepos) {
        if (activeRepoName === repo.repo_full_name) {
          // Trigger the build
          handleBuildIdea(repo.repo_full_name, activeIdStr);
          break;
        }
      }
    }

    // Handle reordering within Ideas column
    // (Would need more complex logic for cross-repo or cross-column reordering)
  }, [savedRepos, activeRepoName, handleBuildIdea]);

  const handleRemoveRepo = (repoFullName: string) => {
    removeSavedRepo.mutate(repoFullName);
  };

  if (isLoadingRepos) {
    return (
      <div className="flex gap-6 overflow-x-auto h-full px-6 pb-6">
        {[1, 2].map((i) => (
          <div key={i} className="flex-shrink-0">
            <div className="h-8 w-48 bg-[#26282D] rounded mb-4 animate-pulse" />
            <div className="flex gap-4">
              <div className="w-[280px] h-[300px] bg-[#1E1F22] rounded-xl animate-pulse" />
              <div className="w-[280px] h-[300px] bg-[#1E1F22] rounded-xl animate-pulse" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCorners}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
    >
      <div className="flex gap-8 overflow-x-auto h-full px-6 pb-6 custom-scrollbar-always">
        {savedRepos.map((repo) => (
          <React.Fragment key={repo.repo_full_name}>
            <BuildIdeaMutationWrapper repoFullName={repo.repo_full_name} />
            <RepoColumns
              repo={repo}
              onRemove={() => handleRemoveRepo(repo.repo_full_name)}
            />
          </React.Fragment>
        ))}

        {/* Add Repo Card */}
        <div className="flex-shrink-0 self-start">
          <AddRepoCard onClick={onAddRepo} />
        </div>
      </div>

      {/* Drag Overlay - shows the dragged item */}
      <DragOverlay>
        {activeId && activeRepoName ? (
          <DragOverlayContent activeId={activeId} repoFullName={activeRepoName} />
        ) : null}
      </DragOverlay>
    </DndContext>
  );
}
