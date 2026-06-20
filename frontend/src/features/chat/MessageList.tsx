import { useEffect, useRef } from 'react';

import type { Message } from '@/lib/api/chat';
import type { DraftMessage } from './useStreamingChat';
import { MessageBubble } from './MessageBubble';
import { Skeleton } from '@/components/ui/skeleton';

interface Props {
  messages: Message[];
  draft: DraftMessage | null;
  pendingUserText?: string | null;
  pendingImagePreviewUrl?: string | null;
}

/** Pulsing placeholder bubbles. Shown when a session is selected but its messages are still
 *  being fetched — keeps the chat surface non-empty so it doesn't look like a fresh session. */
export function MessageListSkeleton() {
  return (
    <div className="flex-1 overflow-y-auto scroll-area-thin">
      <div className="mx-auto max-w-3xl space-y-6 px-4 py-6">
        {[
          { side: 'user', w: 'w-2/3' },
          { side: 'assistant', w: 'w-3/4' },
          { side: 'user', w: 'w-1/2' },
          { side: 'assistant', w: 'w-4/5' },
        ].map((row, i) => (
          <div key={i} className={`flex ${row.side === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`flex flex-col gap-2 ${row.w}`}>
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-5/6" />
              {row.side === 'assistant' && <Skeleton className="h-4 w-3/4" />}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function MessageList({ messages, draft, pendingUserText, pendingImagePreviewUrl }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages.length, draft?.text.length, draft?.tools.length]);

  // Dedupe: backend persists the user message BEFORE streaming, so a refetch mid-stream
  // can land it in the cache while we're still rendering the optimistic pending bubble.
  // If the last user-row in `messages` matches `pendingUserText`, skip the pending bubble.
  const lastMsg = messages[messages.length - 1];
  const pendingMatchesCache =
    pendingUserText !== null &&
    lastMsg?.role === 'user' &&
    lastMsg.content === pendingUserText;
  const showPendingUser =
    pendingUserText !== null &&
    !pendingMatchesCache &&
    draft !== null &&
    draft.phase !== 'idle' &&
    draft.phase !== 'done' &&
    draft.phase !== 'error';

  return (
    <div className="flex-1 overflow-y-auto scroll-area-thin">
      <div className="mx-auto max-w-3xl divide-y divide-transparent">
        {messages.map((m) => (
          <MessageBubble
            key={m.id}
            role={m.role === 'assistant' ? 'assistant' : 'user'}
            text={m.content}
            imagePath={m.image_path}
          />
        ))}
        {showPendingUser && (
          <MessageBubble
            role="user"
            text={pendingUserText!}
            imagePreviewUrl={pendingImagePreviewUrl ?? undefined}
          />
        )}
        {draft &&
          (draft.text ||
            draft.tools.length ||
            draft.phase === 'thinking' ||
            draft.phase === 'starting' ||
            draft.phase === 'error') && (
            <MessageBubble role="assistant" text={draft.text} draft={draft} />
          )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
