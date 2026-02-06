import React from "react";
import { PrefetchPageLinks } from "react-router";
import { useSavedRepos } from "#/hooks/query/use-saved-repos";
import { useRemoveSavedRepo } from "#/hooks/mutation/use-saved-repos-mutations";
import { usePaginatedConversations } from "#/hooks/query/use-paginated-conversations";
import { RepoCard, AddRepoCard, AddRepoModal } from "#/components/features/home/repo-card";
import { useUserProviders } from "#/hooks/use-user-providers";
import { ConnectToProviderMessage } from "#/components/features/home/connect-to-provider-message";

<PrefetchPageLinks page="/conversations/:conversationId" />;

function HomeScreen() {
  const [isAddModalOpen, setIsAddModalOpen] = React.useState(false);
  
  const { providers } = useUserProviders();
  const { data: savedRepos = [], isLoading: isLoadingRepos } = useSavedRepos();
  const { data: conversationsData } = usePaginatedConversations();
  const removeSavedRepo = useRemoveSavedRepo();

  const conversations = conversationsData?.pages.flatMap((page) => page.results) || [];
  const providersAreSet = providers.length > 0;

  const handleRemoveRepo = (repoFullName: string) => {
    removeSavedRepo.mutate(repoFullName);
  };

  return (
    <div
      data-testid="home-screen"
      className="px-0 pt-4 bg-transparent h-full flex flex-col pt-[35px] overflow-y-auto rounded-xl lg:px-[42px] lg:pt-[42px] custom-scrollbar-always"
    >
      {/* Header */}
      <div className="px-6 lg:px-0 mb-8">
        <h1 className="text-2xl font-bold text-white mb-2">
          Let's Start Building!
        </h1>
        <p className="text-[#A3A3A3] text-sm">
          {savedRepos.length > 0
            ? "Click 'New Conversation' on any repository to get started instantly."
            : "Add a repository to get started with pre-warmed conversations."}
        </p>
      </div>

      {/* Provider Setup Message */}
      {!providersAreSet && (
        <div className="px-6 lg:px-0 mb-6">
          <div className="p-6 rounded-xl border border-[#727987] bg-[#26282D]">
            <ConnectToProviderMessage />
          </div>
        </div>
      )}

      {/* Repository Cards Grid */}
      {providersAreSet && (
        <div className="px-6 lg:px-0">
          <div className="flex flex-wrap gap-4">
            {/* Existing Repo Cards */}
            {isLoadingRepos ? (
              // Loading skeleton
              <div className="flex gap-4">
                {[1, 2].map((i) => (
                  <div
                    key={i}
                    className="animate-pulse bg-[#26282D] rounded-xl border border-[#727987] min-w-[280px] max-w-[340px] h-[200px]"
                  />
                ))}
              </div>
            ) : (
              savedRepos.map((repo) => (
                <RepoCard
                  key={repo.repo_full_name}
                  repo={repo}
                  conversations={conversations}
                  onRemove={() => handleRemoveRepo(repo.repo_full_name)}
                />
              ))
            )}

            {/* Add Repo Card */}
            <AddRepoCard onClick={() => setIsAddModalOpen(true)} />
          </div>
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
