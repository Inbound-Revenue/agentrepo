/**
 * Types for the Repository Ideas API
 */

export type BuildingStatus = 'running' | 'review' | 'error' | 'queued' | null;

export interface RepoIdea {
  id: string;
  repo_full_name: string;
  user_id: string;
  text: string;
  order: number;
  created_at: string;
  updated_at: string;
  building_conversation_id: string | null;
  building_status: BuildingStatus;
  building_started_at: string | null;
  building_error_message: string | null;
}

export interface CreateIdeaRequest {
  text: string;
}

export interface UpdateIdeaRequest {
  text?: string;
}

export interface ReorderIdeasRequest {
  idea_ids: string[];
}

export interface BuildIdeaResponse {
  idea_id: string;
  conversation_id: string | null;
  status: 'running' | 'queued' | 'error';
  message: string | null;
}
