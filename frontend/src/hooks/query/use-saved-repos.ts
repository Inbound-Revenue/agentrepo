/**
 * React Query hook for fetching saved repositories
 */

import { useQuery } from "@tanstack/react-query";
import SavedReposService from "#/api/saved-repos-service/saved-repos-service.api";
import type { SavedRepository } from "#/api/saved-repos-service/saved-repos.types";

export const SAVED_REPOS_QUERY_KEY = ["saved-repos"];

export const useSavedRepos = () => {
  return useQuery<SavedRepository[], Error>({
    queryKey: SAVED_REPOS_QUERY_KEY,
    queryFn: SavedReposService.getSavedRepos,
    refetchOnWindowFocus: false,
    staleTime: 1000 * 60 * 2, // 2 minutes
    gcTime: 1000 * 60 * 10, // 10 minutes
  });
};

export const useSavedRepo = (repoFullName: string | undefined) => {
  return useQuery<SavedRepository, Error>({
    queryKey: [...SAVED_REPOS_QUERY_KEY, repoFullName],
    queryFn: () => SavedReposService.getSavedRepo(repoFullName!),
    enabled: !!repoFullName,
    refetchOnWindowFocus: false,
    staleTime: 1000 * 60 * 2,
    gcTime: 1000 * 60 * 10,
  });
};

export const usePoolStatus = () => {
  return useQuery({
    queryKey: [...SAVED_REPOS_QUERY_KEY, "pool-status"],
    queryFn: SavedReposService.getPoolStatus,
    refetchInterval: 5000, // Poll every 5 seconds for status updates
    refetchOnWindowFocus: true,
    staleTime: 1000 * 2, // 2 seconds
  });
};
