/**
 * Types for the Saved Repos API
 */

export type WarmingStep = 'queued' | 'initializing' | 'cloning_repo' | 'building_runtime' | 'starting_agent' | 'ready' | 'error';

export interface PrewarmedConversation {
  conversation_id: string;
  status: 'pending' | 'warming' | 'ready' | 'error';
  created_at: string;
  error_message: string | null;
  warming_step: WarmingStep | null;
}

export interface SavedRepository {
  repo_full_name: string;
  branch: string;
  git_provider: string;
  added_at: string;
  last_commit_sha: string | null;
  pool_size: number;
  prewarmed_conversations: PrewarmedConversation[];
  ready_count: number;
  warming_count: number;
}

export interface AddRepoRequest {
  repo_full_name: string;
  branch?: string;
  git_provider?: string;
  pool_size?: number;
}

export interface UpdateRepoRequest {
  branch?: string;
  last_commit_sha?: string;
  pool_size?: number;
}

export interface ClaimConversationResponse {
  conversation_id: string;
  repo_full_name: string;
  branch: string;
}

export interface PoolStatus {
  initialized: boolean;
  repos: {
    repo_full_name: string;
    branch: string;
    pool_size: number;
    ready_count: number;
    warming_count: number;
    conversations: PrewarmedConversation[];
  }[];
}
