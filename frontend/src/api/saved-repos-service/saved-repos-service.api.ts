/**
 * API service for managing saved repositories
 */

import { openHands } from "../open-hands-axios";
import type {
  SavedRepository,
  AddRepoRequest,
  UpdateRepoRequest,
  ClaimConversationResponse,
  PoolStatus,
} from "./saved-repos.types";

const SavedReposService = {
  /**
   * Get all saved repositories
   */
  async getSavedRepos(): Promise<SavedRepository[]> {
    const response = await openHands.get<SavedRepository[]>("/api/saved-repos");
    return response.data;
  },

  /**
   * Get a single saved repository by full name
   */
  async getSavedRepo(repoFullName: string): Promise<SavedRepository> {
    const response = await openHands.get<SavedRepository>(
      `/api/saved-repos/${encodeURIComponent(repoFullName)}`,
    );
    return response.data;
  },

  /**
   * Add a new repository to the saved list
   */
  async addSavedRepo(request: AddRepoRequest): Promise<SavedRepository> {
    const response = await openHands.post<SavedRepository>(
      "/api/saved-repos",
      request,
    );
    return response.data;
  },

  /**
   * Update an existing saved repository
   */
  async updateSavedRepo(
    repoFullName: string,
    request: UpdateRepoRequest,
  ): Promise<SavedRepository> {
    const response = await openHands.patch<SavedRepository>(
      `/api/saved-repos/${encodeURIComponent(repoFullName)}`,
      request,
    );
    return response.data;
  },

  /**
   * Remove a repository from the saved list
   */
  async removeSavedRepo(repoFullName: string): Promise<void> {
    await openHands.delete(`/api/saved-repos/${encodeURIComponent(repoFullName)}`);
  },

  /**
   * Claim a pre-warmed conversation for a repository
   * Returns the conversation ID to redirect to
   */
  async claimConversation(
    repoFullName: string,
  ): Promise<ClaimConversationResponse> {
    const response = await openHands.post<ClaimConversationResponse>(
      `/api/saved-repos/${encodeURIComponent(repoFullName)}/claim`,
    );
    return response.data;
  },

  /**
   * Trigger pre-warming for a repository
   */
  async triggerPrewarm(repoFullName: string): Promise<void> {
    await openHands.post(
      `/api/saved-repos/${encodeURIComponent(repoFullName)}/prewarm`,
    );
  },

  /**
   * Get the status of all conversation pools
   */
  async getPoolStatus(): Promise<PoolStatus> {
    const response = await openHands.get<PoolStatus>(
      "/api/saved-repos/pool-status",
    );
    return response.data;
  },
};

export default SavedReposService;
