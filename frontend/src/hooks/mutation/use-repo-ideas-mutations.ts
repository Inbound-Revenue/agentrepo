import { useMutation, useQueryClient } from "@tanstack/react-query";
import { RepoIdeasService } from "#/api/repo-ideas-service";
import type {
  CreateIdeaRequest,
  UpdateIdeaRequest,
  ReorderIdeasRequest,
} from "#/api/repo-ideas-service";
import toast from "react-hot-toast";

/**
 * Hook to create a new idea
 */
export function useCreateIdea(repoFullName: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: CreateIdeaRequest) =>
      RepoIdeasService.createIdea(repoFullName, request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["repo-ideas", repoFullName] });
    },
    onError: () => {
      toast.error("Failed to create idea");
    },
  });
}

/**
 * Hook to update an existing idea
 */
export function useUpdateIdea(repoFullName: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ ideaId, request }: { ideaId: string; request: UpdateIdeaRequest }) =>
      RepoIdeasService.updateIdea(repoFullName, ideaId, request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["repo-ideas", repoFullName] });
    },
    onError: () => {
      toast.error("Failed to update idea");
    },
  });
}

/**
 * Hook to delete an idea
 */
export function useDeleteIdea(repoFullName: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (ideaId: string) =>
      RepoIdeasService.deleteIdea(repoFullName, ideaId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["repo-ideas", repoFullName] });
    },
    onError: () => {
      toast.error("Failed to delete idea");
    },
  });
}

/**
 * Hook to reorder ideas
 */
export function useReorderIdeas(repoFullName: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: ReorderIdeasRequest) =>
      RepoIdeasService.reorderIdeas(repoFullName, request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["repo-ideas", repoFullName] });
    },
    onError: () => {
      toast.error("Failed to reorder ideas");
    },
  });
}

/**
 * Hook to build an idea (start working on it)
 */
export function useBuildIdea(repoFullName: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (ideaId: string) =>
      RepoIdeasService.buildIdea(repoFullName, ideaId),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["repo-ideas", repoFullName] });
      
      if (data.status === "queued") {
        toast(data.message || "Request queued - agent will start when ready", {
          icon: "⏳",
          duration: 5000,
        });
      } else if (data.status === "running") {
        toast.success("Agent started working on your idea!");
      } else if (data.status === "error") {
        toast.error(data.message || "Failed to start build");
      }
    },
    onError: () => {
      toast.error("Failed to start build");
    },
  });
}

/**
 * Hook to update an idea's building status
 */
export function useUpdateIdeaStatus(repoFullName: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ ideaId, status, errorMessage }: { 
      ideaId: string; 
      status: string; 
      errorMessage?: string 
    }) =>
      RepoIdeasService.updateIdeaStatus(repoFullName, ideaId, status, errorMessage),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["repo-ideas", repoFullName] });
    },
  });
}
