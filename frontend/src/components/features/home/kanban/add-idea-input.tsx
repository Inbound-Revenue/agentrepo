/**
 * Auto-growing text input for adding new ideas
 */

import React from "react";
import { useCreateIdea } from "#/hooks/mutation/use-repo-ideas-mutations";

interface AddIdeaInputProps {
  repoFullName: string;
}

export function AddIdeaInput({ repoFullName }: AddIdeaInputProps) {
  const [text, setText] = React.useState("");
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);
  const createIdea = useCreateIdea(repoFullName);

  // Auto-resize textarea as content grows
  const adjustHeight = () => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = "auto";
      textarea.style.height = `${Math.min(textarea.scrollHeight, 150)}px`;
    }
  };

  React.useEffect(() => {
    adjustHeight();
  }, [text]);

  const handleBlur = () => {
    const trimmedText = text.trim();
    if (trimmedText) {
      createIdea.mutate(
        { text: trimmedText },
        {
          onSuccess: () => {
            setText("");
          },
        },
      );
    }
  };

  const handleSubmit = () => {
    const trimmedText = text.trim();
    if (trimmedText) {
      createIdea.mutate(
        { text: trimmedText },
        {
          onSuccess: () => {
            setText("");
          },
        },
      );
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Shift+Enter for new line, Enter to submit
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <textarea
      ref={textareaRef}
      value={text}
      onChange={(e) => setText(e.target.value)}
      onBlur={handleBlur}
      onKeyDown={handleKeyDown}
      placeholder="Add an idea or issue..."
      disabled={createIdea.isPending}
      className="w-full bg-[#26282D] hover:bg-[#2A2C31] focus:bg-[#2A2C31] rounded-lg p-3 text-white text-sm placeholder-[#6B7280] resize-none outline-none border border-transparent focus:border-[#525664] transition-colors mt-2 min-h-[44px]"
      rows={1}
    />
  );
}
