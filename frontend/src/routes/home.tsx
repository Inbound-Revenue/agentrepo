import React from "react";
import { PrefetchPageLinks } from "react-router";
import { KanbanBoard } from "#/components/features/home/kanban";
import { AddRepoModal } from "#/components/features/home/repo-card";
import { useUserProviders } from "#/hooks/use-user-providers";
import { ConnectToProviderMessage } from "#/components/features/home/connect-to-provider-message";
import { useSavedRepos } from "#/hooks/query/use-saved-repos";

<PrefetchPageLinks page="/conversations/:conversationId" />;

function HomeScreen() {
  const [isAddModalOpen, setIsAddModalOpen] = React.useState(false);

  const { providers } = useUserProviders();
  const { data: savedRepos = [] } = useSavedRepos();
  const providersAreSet = providers.length > 0;

  return (
    <div
      data-testid="home-screen"
      className="bg-transparent h-full flex flex-col pt-[35px] overflow-hidden rounded-xl"
    >
      {/* Header */}
      <div className="px-6 lg:px-[42px] mb-6">
        {/* eslint-disable-next-line i18next/no-literal-string */}
        <h1 className="text-2xl font-bold text-white mb-2">Agent Dashboard</h1>
        <p className="text-[#A3A3A3] text-sm">
          {/* eslint-disable-next-line i18next/no-literal-string */}
          {savedRepos.length > 0
            ? "Manage your agents across repositories. Drag ideas to 'Building' to start working."
            : "Add a repository to get started with AI-powered development."}
        </p>
      </div>

      {/* Provider Setup Message */}
      {!providersAreSet && (
        <div className="px-6 lg:px-[42px] mb-6">
          <div className="p-6 rounded-xl border border-[#727987] bg-[#26282D]">
            <ConnectToProviderMessage />
          </div>
        </div>
      )}

      {/* Kanban Board */}
      {providersAreSet && (
        <div className="flex-1 overflow-hidden">
          <KanbanBoard onAddRepo={() => setIsAddModalOpen(true)} />
        </div>
      )}

      {/* Add Repo Modal */}
      <AddRepoModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
      />
    </div>
  );
}

export default HomeScreen;
