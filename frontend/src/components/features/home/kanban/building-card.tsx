/**
 * Card showing a building task with its status
 */

import React from "react";
import { useNavigate } from "react-router";
import type { RepoIdea } from "#/api/repo-ideas-service";
import { useConversationSubscriptions } from "#/context/conversation-subscriptions-provider";
import { useUpdateIdeaStatus } from "#/hooks/mutation/use-repo-ideas-mutations";
import { AgentState } from "#/types/agent-state";
import { isOpenHandsEvent, isAgentStateChangeObservation } from "#/types/core/guards";

interface BuildingCardProps {
  idea: RepoIdea;
  repoFullName: string;
}

export function BuildingCard({ idea, repoFullName }: BuildingCardProps) {
  const navigate = useNavigate();
  const { subscribeToConversation, unsubscribeFromConversation, isSubscribedToConversation } =
    useConversationSubscriptions();
  const updateStatus = useUpdateIdeaStatus(repoFullName);
  const [localStatus, setLocalStatus] = React.useState(idea.building_status);

  // Sync local status with prop
  React.useEffect(() => {
    setLocalStatus(idea.building_status);
  }, [idea.building_status]);

  // Subscribe to conversation for status updates
  React.useEffect(() => {
    if (
      idea.building_conversation_id &&
      localStatus === "running" &&
      !isSubscribedToConversation(idea.building_conversation_id)
    ) {
      subscribeToConversation({
        conversationId: idea.building_conversation_id,
        sessionApiKey: null,
        providersSet: [],
        baseUrl: window.location.origin,
        onEvent: (event) => {
          if (isOpenHandsEvent(event) && isAgentStateChangeObservation(event)) {
            const agentState = event.extras.agent_state;
            if (
              agentState === AgentState.FINISHED ||
              agentState === AgentState.AWAITING_USER_INPUT
            ) {
              setLocalStatus("review");
              // Update backend
              updateStatus.mutate({
                ideaId: idea.id,
                status: "review",
              });
              // Unsubscribe since we got the final state
              if (idea.building_conversation_id) {
                unsubscribeFromConversation(idea.building_conversation_id);
              }
            } else if (agentState === AgentState.ERROR) {
              setLocalStatus("error");
              updateStatus.mutate({
                ideaId: idea.id,
                status: "error",
                errorMessage: "Agent encountered an error",
              });
              if (idea.building_conversation_id) {
                unsubscribeFromConversation(idea.building_conversation_id);
              }
            }
          }
        },
      });
    }

    // Cleanup on unmount
    return () => {
      if (idea.building_conversation_id && isSubscribedToConversation(idea.building_conversation_id)) {
        unsubscribeFromConversation(idea.building_conversation_id);
      }
    };
  }, [idea.building_conversation_id, localStatus]);

  const handleClick = () => {
    if (idea.building_conversation_id) {
      navigate(`/conversations/${idea.building_conversation_id}`);
    }
  };

  const handleRetry = (e: React.MouseEvent) => {
    e.stopPropagation();
    // Reset status to trigger a new build
    setLocalStatus("running");
    updateStatus.mutate({
      ideaId: idea.id,
      status: "running",
    });
  };

  const getStatusBadge = () => {
    switch (localStatus) {
      case "running":
        return (
          <span className="flex items-center gap-1.5 text-yellow-400 text-xs">
            <span className="inline-block w-3 h-3 border-2 border-yellow-400 border-t-transparent rounded-full animate-spin" />
            {/* eslint-disable-next-line i18next/no-literal-string */}
            <span>Running...</span>
          </span>
        );
      case "review":
        return (
          <span className="flex items-center gap-1 text-green-400 text-xs">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
              <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" />
            </svg>
            {/* eslint-disable-next-line i18next/no-literal-string */}
            <span>Ready for Review</span>
          </span>
        );
      case "error": {
        const errorLabel = "Error";
        const retryLabel = "Retry";
        return (
          <span className="flex items-center gap-1 text-red-400 text-xs">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z" />
            </svg>
            <span>{errorLabel}</span>
            <button
              type="button"
              onClick={handleRetry}
              className="ml-1 text-blue-400 hover:text-blue-300 underline"
              aria-label="Retry build"
            >
              {retryLabel}
            </button>
          </span>
        );
      }
      case "queued":
        return (
          <span className="flex items-center gap-1.5 text-blue-400 text-xs">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10 10-4.5 10-10S17.5 2 12 2zm4.2 14.2L11 13V7h1.5v5.2l4.5 2.7-.8 1.3z" />
            </svg>
            {/* eslint-disable-next-line i18next/no-literal-string */}
            <span>Queued</span>
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <div
      onClick={handleClick}
      className="bg-[#26282D] rounded-lg p-3 cursor-pointer hover:bg-[#2A2C31] transition-colors"
    >
      <p className="text-white text-sm truncate mb-2" title={idea.text}>
        {idea.text.length > 60 ? `${idea.text.substring(0, 60)}...` : idea.text}
      </p>
      {getStatusBadge()}
      {idea.building_error_message && localStatus === "error" && (
        <p className="text-red-400 text-xs mt-1 truncate" title={idea.building_error_message}>
          {idea.building_error_message}
        </p>
      )}
    </div>
  );
}
