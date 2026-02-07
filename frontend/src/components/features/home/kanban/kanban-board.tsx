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
import { sortableKeyboardCoordinates, arrayMove } from "@dnd-kit/sortable";
import { useSavedRepos } from "#/hooks/query/use-saved-repos";
import { useRepoIdeas } from "#/hooks/query/use-repo-ideas";
import { useBuildIdea, useReorderIdeas } from "#/hooks/mutation/use-repo-ideas-mutations";
import { RepoColumns } from "./repo-columns";
import { AddRepoCard } from "#/components/features/home/repo-card";
import { useRemoveSavedRepo } from "#/hooks/mutation/use-saved-repos-mutations";
import { useQueryClient } from "@tanstack/react-query";
import type { RepoIdea } from "#/api/repo-ideas-service";

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

interface ReorderIdeasEvent extends CustomEvent {
  detail: { repoFullName: string; ideaIds: string[] };
}

/**
 * Wrapper component to handle reorder mutations per repo
 */
function ReorderMutationWrapper({ repoFullName }: { repoFullName: string }) {
  const reorderIdeas = useReorderIdeas(repoFullName);

  React.useEffect(() => {
    const handleReorderEvent = (event: Event) => {
      const customEvent = event as ReorderIdeasEvent;
      if (customEvent.detail.repoFullName === repoFullName) {
        reorderIdeas.mutate({ idea_ids: customEvent.detail.ideaIds });
      }
    };

    window.addEventListener("reorder-ideas", handleReorderEvent);
    return () => {
      window.removeEventListener("reorder-ideas", handleReorderEvent);
    };
  }, [repoFullName, reorderIdeas]);

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
  const queryClient = useQueryClient();
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

  const handleReorderIdeas = React.useCallback((repoFullName: string, ideaIds: string[]) => {
    // Dispatch event to trigger reorder mutation
    const event = new CustomEvent("reorder-ideas", {
      detail: { repoFullName, ideaIds },
    });
    window.dispatchEvent(event);
  }, []);

  const handleDragStart = React.useCallback((event: DragStartEvent) => {
    const { active } = event;
    setActiveId(active.id as string);

    // Find which repo this idea belongs to by checking the sortable data
    const activeData = active.data.current;
    if (activeData?.sortable?.containerId) {
      const containerId = activeData.sortable.containerId as string;
      if (containerId.startsWith("ideas-")) {
        setActiveRepoName(containerId.replace("ideas-", ""));
      }
    } else if (savedRepos.length > 0) {
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

    // Get the repo name from the active item's sortable data
    const activeData = active.data.current;
    let repoFullName: string | null = null;
    
    if (activeData?.sortable?.containerId) {
      const containerId = activeData.sortable.containerId as string;
      if (containerId.startsWith("ideas-")) {
        repoFullName = containerId.replace("ideas-", "");
      }
    }

    if (!repoFullName) return;

    // Check if dropped on a "Building" column
    if (overIdStr.startsWith("building-")) {
      handleBuildIdea(repoFullName, activeIdStr);
      return;
    }

    // Handle reordering within Ideas column
    if (activeIdStr !== overIdStr) {
      const ideas = queryClient.getQueryData<RepoIdea[]>(["repo-ideas", repoFullName]);
      if (ideas) {
        // Only reorder ideas that are NOT building (in the ideas column)
        const ideasOnly = ideas.filter((i) => !i.building_conversation_id);
        const oldIndex = ideasOnly.findIndex((i) => i.id === activeIdStr);
        const newIndex = ideasOnly.findIndex((i) => i.id === overIdStr);
        
        if (oldIndex !== -1 && newIndex !== -1 && oldIndex !== newIndex) {
          const reorderedIdeas = arrayMove(ideasOnly, oldIndex, newIndex);
          const newOrder = reorderedIdeas.map((i) => i.id);
          
          // Optimistically update the cache
          const buildingIdeas = ideas.filter((i) => i.building_conversation_id);
          const updatedIdeasOnly = reorderedIdeas.map((idea, index) => ({
            ...idea,
            order: index,
          }));
          queryClient.setQueryData(
            ["repo-ideas", repoFullName],
            [...updatedIdeasOnly, ...buildingIdeas]
          );
          
          // Trigger the reorder mutation
          handleReorderIdeas(repoFullName, newOrder);
        }
      }
    }
  }, [handleBuildIdea, handleReorderIdeas, queryClient]);

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
            <ReorderMutationWrapper repoFullName={repo.repo_full_name} />
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
