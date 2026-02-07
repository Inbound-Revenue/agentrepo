/**
 * API service for managing repository ideas
 */

import { openHands } from "../open-hands-axios";
import type {
  RepoIdea,
  CreateIdeaRequest,
  UpdateIdeaRequest,
  ReorderIdeasRequest,
  BuildIdeaResponse,
} from "./repo-ideas.types";

const RepoIdeasService = {
  /**
   * Get all ideas for a repository
   */
  async getIdeas(repoFullName: string): Promise<RepoIdea[]> {
    const response = await openHands.get<RepoIdea[]>(
      `/api/saved-repos/${encodeURIComponent(repoFullName)}/ideas`,
    );
    return response.data;
  },

  /**
   * Create a new idea for a repository
   */
  async createIdea(
    repoFullName: string,
    request: CreateIdeaRequest,
  ): Promise<RepoIdea> {
    const response = await openHands.post<RepoIdea>(
      `/api/saved-repos/${encodeURIComponent(repoFullName)}/ideas`,
      request,
    );
    return response.data;
  },

  /**
   * Update an existing idea
   */
  async updateIdea(
    repoFullName: string,
    ideaId: string,
    request: UpdateIdeaRequest,
  ): Promise<RepoIdea> {
    const response = await openHands.patch<RepoIdea>(
      `/api/saved-repos/${encodeURIComponent(repoFullName)}/ideas/${ideaId}`,
      request,
    );
    return response.data;
  },

  /**
   * Delete an idea
   */
  async deleteIdea(repoFullName: string, ideaId: string): Promise<void> {
    await openHands.delete(
      `/api/saved-repos/${encodeURIComponent(repoFullName)}/ideas/${ideaId}`,
    );
  },

  /**
   * Reorder ideas for a repository
   */
  async reorderIdeas(
    repoFullName: string,
    request: ReorderIdeasRequest,
  ): Promise<RepoIdea[]> {
    const response = await openHands.post<RepoIdea[]>(
      `/api/saved-repos/${encodeURIComponent(repoFullName)}/ideas/reorder`,
      request,
    );
    return response.data;
  },

  /**
   * Start building an idea (claim conversation and send prompt)
   */
  async buildIdea(
    repoFullName: string,
    ideaId: string,
  ): Promise<BuildIdeaResponse> {
    const response = await openHands.post<BuildIdeaResponse>(
      `/api/saved-repos/${encodeURIComponent(repoFullName)}/ideas/${ideaId}/build`,
    );
    return response.data;
  },

  /**
   * Update the building status of an idea
   */
  async updateIdeaStatus(
    repoFullName: string,
    ideaId: string,
    status: string,
    errorMessage?: string,
  ): Promise<RepoIdea> {
    const params = new URLSearchParams({ status_value: status });
    if (errorMessage) {
      params.append("error_message", errorMessage);
    }
    const response = await openHands.patch<RepoIdea>(
      `/api/saved-repos/${encodeURIComponent(repoFullName)}/ideas/${ideaId}/status?${params.toString()}`,
    );
    return response.data;
  },
};

export default RepoIdeasService;
