/**
 * AddRepoCard - A card that opens a modal to add a new repository
 */

import { useTranslation } from "react-i18next";
import PlusIcon from "#/icons/plus.svg?react";
import { I18nKey } from "#/i18n/declaration";

interface AddRepoCardProps {
  onClick: () => void;
}

export function AddRepoCard({ onClick }: AddRepoCardProps) {
  const { t } = useTranslation();
  
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex flex-col items-center justify-center gap-3 p-5 rounded-xl border-2 border-dashed border-[#727987] bg-transparent hover:bg-[#26282D] hover:border-[#4D6DFF] min-w-[280px] max-w-[340px] min-h-[180px] transition-all cursor-pointer group"
    >
      <div className="w-12 h-12 rounded-full bg-[#3D3F45] group-hover:bg-[#4D6DFF] flex items-center justify-center transition-colors">
        <PlusIcon
          width={24}
          height={24}
          className="text-[#A3A3A3] group-hover:text-white transition-colors"
        />
      </div>
      <span className="text-[#A3A3A3] group-hover:text-white font-medium text-sm transition-colors">
        {t(I18nKey.COMMON$ADD_REPOSITORY)}
      </span>
    </button>
  );
}
