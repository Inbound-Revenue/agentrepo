/**
 * AddRepoModal - Modal to add a new repository to saved repos
 */

import React from "react";
import { useTranslation } from "react-i18next";
import { useUserProviders } from "#/hooks/use-user-providers";
import { useAddSavedRepo } from "#/hooks/mutation/use-saved-repos-mutations";
import { Branch, GitRepository } from "#/types/git";
import { Provider } from "#/types/settings";
import { I18nKey } from "#/i18n/declaration";
import { GitProviderDropdown } from "../git-provider-dropdown";
import { GitBranchDropdown } from "../git-branch-dropdown";
import { GitRepoDropdown } from "../git-repo-dropdown";
import { BrandButton } from "../../settings/brand-button";
import RepoForkedIcon from "#/icons/repo-forked.svg?react";

interface AddRepoModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function AddRepoModal({ isOpen, onClose }: AddRepoModalProps) {
  const { t } = useTranslation();
  const { providers } = useUserProviders();
  const addSavedRepo = useAddSavedRepo();

  const [selectedRepository, setSelectedRepository] =
    React.useState<GitRepository | null>(null);
  const [selectedBranch, setSelectedBranch] = React.useState<Branch | null>(
    null,
  );
  const [selectedProvider, setSelectedProvider] =
    React.useState<Provider | null>(null);
  const [poolSize, setPoolSize] = React.useState(2);

  // Auto-select provider if only one available
  React.useEffect(() => {
    if (providers.length === 1 && !selectedProvider) {
      setSelectedProvider(providers[0]);
    }
  }, [providers, selectedProvider]);

  const handleProviderSelection = (provider: Provider | null) => {
    if (provider === selectedProvider) return;
    setSelectedProvider(provider);
    setSelectedRepository(null);
    setSelectedBranch(null);
  };

  const handleRepoSelection = (repository?: GitRepository) => {
    if (repository) {
      setSelectedRepository(repository);
    } else {
      setSelectedRepository(null);
      setSelectedBranch(null);
    }
  };

  const handleBranchSelection = (branch: Branch | null) => {
    setSelectedBranch(branch);
  };

  const handleSubmit = () => {
    if (!selectedRepository || !selectedBranch) return;

    addSavedRepo.mutate(
      {
        repo_full_name: selectedRepository.full_name,
        branch: selectedBranch.name,
        git_provider: selectedRepository.git_provider || "github",
        pool_size: poolSize,
      },
      {
        onSuccess: () => {
          // Reset form and close modal
          setSelectedRepository(null);
          setSelectedBranch(null);
          setPoolSize(2);
          onClose();
        },
      },
    );
  };

  const handleClose = () => {
    setSelectedRepository(null);
    setSelectedBranch(null);
    setPoolSize(2);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60"
        onClick={handleClose}
        onKeyDown={(e) => e.key === "Escape" && handleClose()}
        role="button"
        tabIndex={0}
        aria-label="Close modal"
      />

      {/* Modal */}
      <div className="relative z-10 bg-[#26282D] rounded-xl border border-[#727987] p-6 w-full max-w-md mx-4 shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <RepoForkedIcon width={24} height={24} className="text-white" />
            <h2 className="text-lg font-bold text-white">Add Repository</h2>
          </div>
          <button
            onClick={handleClose}
            className="text-[#A3A3A3] hover:text-white transition-colors"
            aria-label="Close"
          >
            <svg
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Form */}
        <div className="flex flex-col gap-4">
          {/* Provider Selector */}
          {providers.length > 1 && (
            <div>
              <label className="block text-sm text-[#A3A3A3] mb-2">
                Provider
              </label>
              <GitProviderDropdown
                providers={providers}
                value={selectedProvider}
                placeholder="Select Provider"
                className="w-full"
                onChange={handleProviderSelection}
              />
            </div>
          )}

          {/* Repository Selector */}
          <div>
            <label className="block text-sm text-[#A3A3A3] mb-2">
              Repository
            </label>
            <GitRepoDropdown
              provider={selectedProvider || providers[0]}
              value={selectedRepository?.id || null}
              repositoryName={selectedRepository?.full_name || null}
              placeholder="user/repo"
              disabled={!selectedProvider && providers.length > 1}
              onChange={handleRepoSelection}
              className="w-full"
            />
          </div>

          {/* Branch Selector */}
          <div>
            <label className="block text-sm text-[#A3A3A3] mb-2">Branch</label>
            <GitBranchDropdown
              repository={selectedRepository?.full_name || null}
              provider={selectedProvider || providers[0]}
              selectedBranch={selectedBranch}
              onBranchSelect={handleBranchSelection}
              defaultBranch={selectedRepository?.main_branch || null}
              placeholder="Select branch..."
              className="w-full"
              disabled={!selectedRepository}
            />
          </div>

          {/* Pool Size */}
          <div>
            <label className="block text-sm text-[#A3A3A3] mb-2">
              Pre-warmed conversations
            </label>
            <div className="flex items-center gap-3">
              <input
                type="range"
                min="1"
                max="5"
                value={poolSize}
                onChange={(e) => setPoolSize(Number(e.target.value))}
                className="flex-1 accent-[#4D6DFF]"
              />
              <span className="text-white font-medium w-6 text-center">
                {poolSize}
              </span>
            </div>
            <p className="text-xs text-[#6B7280] mt-1">
              Number of conversations to keep ready for instant access
            </p>
          </div>

          {/* Submit Button */}
          <BrandButton
            testId="add-repo-button"
            variant="primary"
            type="button"
            isDisabled={!selectedRepository || !selectedBranch || addSavedRepo.isPending}
            onClick={handleSubmit}
            className="w-full mt-2"
          >
            {addSavedRepo.isPending ? "Adding..." : "Add Repository"}
          </BrandButton>
        </div>
      </div>
    </div>
  );
}
