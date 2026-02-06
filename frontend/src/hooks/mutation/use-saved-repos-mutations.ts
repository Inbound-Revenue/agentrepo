/**
 * React Query mutation hooks for saved repositories
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import SavedReposService from "#/api/saved-repos-service/saved-repos-service.api";
import type {
  AddRepoRequest,
  UpdateRepoRequest,
} from "#/api/saved-repos-service/saved-repos.types";
import { SAVED_REPOS_QUERY_KEY } from "#/hooks/query/use-saved-repos";

/**
 * Hook to add a new saved repository
 */
export const useAddSavedRepo = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: AddRepoRequest) =>
      SavedReposService.addSavedRepo(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: SAVED_REPOS_QUERY_KEY });
    },
  });
};

/**
 * Hook to update a saved repository
 */
export const useUpdateSavedRepo = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      repoFullName,
      request,
    }: {
      repoFullName: string;
      request: UpdateRepoRequest;
    }) => SavedReposService.updateSavedRepo(repoFullName, request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: SAVED_REPOS_QUERY_KEY });
    },
  });
};

/**
 * Hook to remove a saved repository
 */
export const useRemoveSavedRepo = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (repoFullName: string) =>
      SavedReposService.removeSavedRepo(repoFullName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: SAVED_REPOS_QUERY_KEY });
    },
  });
};

/**
 * Hook to claim a pre-warmed conversation and navigate to it
 */
export const useClaimConversation = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (repoFullName: string) =>
      SavedReposService.claimConversation(repoFullName),
    onSuccess: (data) => {
      // Invalidate saved repos to update pool counts
      queryClient.invalidateQueries({ queryKey: SAVED_REPOS_QUERY_KEY });
      // Navigate to the claimed conversation
      navigate(`/conversations/${data.conversation_id}`);
    },
  });
};

/**
 * Hook to trigger pre-warming for a repository
 */
export const useTriggerPrewarm = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (repoFullName: string) =>
      SavedReposService.triggerPrewarm(repoFullName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: SAVED_REPOS_QUERY_KEY });
    },
  });
};
