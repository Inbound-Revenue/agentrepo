/**
 * Draggable card for an idea in the Ideas column
 */

import React from "react";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useUpdateIdea, useDeleteIdea } from "#/hooks/mutation/use-repo-ideas-mutations";
import type { RepoIdea } from "#/api/repo-ideas-service";

interface IdeaCardProps {
  idea: RepoIdea;
  repoFullName: string;
}

export function IdeaCard({ idea, repoFullName }: IdeaCardProps) {
  const [text, setText] = React.useState(idea.text);
  const [isEditing, setIsEditing] = React.useState(false);
  const [isHovered, setIsHovered] = React.useState(false);
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);
  
  const updateIdea = useUpdateIdea(repoFullName);
  const deleteIdea = useDeleteIdea(repoFullName);

  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: idea.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  // Sync local state with prop when it changes
  React.useEffect(() => {
    setText(idea.text);
  }, [idea.text]);

  // Auto-resize textarea
  const adjustHeight = () => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = "auto";
      textarea.style.height = `${Math.min(textarea.scrollHeight, 150)}px`;
    }
  };

  React.useEffect(() => {
    if (isEditing) {
      adjustHeight();
      textareaRef.current?.focus();
    }
  }, [isEditing, text]);

  const handleSave = () => {
    const trimmedText = text.trim();
    if (trimmedText && trimmedText !== idea.text) {
      updateIdea.mutate({ ideaId: idea.id, request: { text: trimmedText } });
    } else {
      setText(idea.text); // Reset to original if empty
    }
    setIsEditing(false);
  };

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    deleteIdea.mutate(idea.id);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      setText(idea.text);
      setIsEditing(false);
    } else if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      handleSave();
    }
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`bg-[#26282D] rounded-lg p-3 cursor-grab active:cursor-grabbing transition-all ${
        isDragging ? "opacity-50 shadow-lg scale-105" : ""
      } ${isEditing ? "ring-1 ring-[#525664]" : ""}`}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      /* eslint-disable react/jsx-props-no-spreading */
      {...attributes}
      {...listeners}
      /* eslint-enable react/jsx-props-no-spreading */
    >
      <div className="flex items-start gap-2">
        <div className="flex-1 min-w-0">
          {isEditing ? (
            <textarea
              ref={textareaRef}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onBlur={handleSave}
              onKeyDown={handleKeyDown}
              className="w-full bg-transparent text-white text-sm resize-none outline-none"
              rows={1}
            />
          ) : (
            <button
              type="button"
              className="text-white text-sm break-words whitespace-pre-wrap text-left w-full bg-transparent border-none p-0 cursor-text"
              onClick={(e) => {
                e.stopPropagation();
                setIsEditing(true);
              }}
            >
              {idea.text}
            </button>
          )}
        </div>
        
        {/* Delete button */}
        {isHovered && !isEditing && (
          <button
            type="button"
            onClick={handleDelete}
            className="flex-shrink-0 text-[#6B7280] hover:text-red-400 transition-colors p-0.5"
            title="Delete idea"
            aria-label="Delete idea"
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}
