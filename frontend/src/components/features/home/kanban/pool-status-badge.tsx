/**
 * Badge showing the pool status (ready/warming counts)
 */

import type { SavedRepository } from "#/api/saved-repos-service/saved-repos.types";

interface PoolStatusBadgeProps {
  repo: SavedRepository;
}

export function PoolStatusBadge({ repo }: PoolStatusBadgeProps) {
  return (
    <span className="text-xs text-[#A3A3A3]">
      {/* eslint-disable-next-line i18next/no-literal-string */}
      {`${repo.ready_count} ready, ${repo.warming_count} warming`}
    </span>
  );
}
