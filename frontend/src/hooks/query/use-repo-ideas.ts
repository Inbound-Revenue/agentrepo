import { useQuery } from "@tanstack/react-query";
import { RepoIdeasService } from "#/api/repo-ideas-service";

/**
 * Hook to fetch ideas for a repository
 */
export function useRepoIdeas(repoFullName: string | undefined) {
  return useQuery({
    queryKey: ["repo-ideas", repoFullName],
    queryFn: () => RepoIdeasService.getIdeas(repoFullName!),
    enabled: !!repoFullName,
    staleTime: 5000, // Consider data fresh for 5 seconds
  });
}
