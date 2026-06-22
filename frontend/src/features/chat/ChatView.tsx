import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Dumbbell, PanelLeftClose, PanelLeftOpen, Sparkles } from 'lucide-react';

import {
  createConversation,
  listMessages,
  uploadPhoto,
  type Conversation,
  type Message,
} from '@/lib/api/chat';
import { useAuthStore } from '@/stores/authStore';
import { useUiStore } from '@/stores/uiStore';
import { useConversations } from '@/hooks/useConversations';
import { Button } from '@/components/ui/button';
import { ConversationSidebar } from './ConversationSidebar';
import { MessageList, MessageListSkeleton } from './MessageList';
import { Composer } from './Composer';
import { useStreamingChat } from './useStreamingChat';

function formatError(err: unknown): string {
  if (typeof err === 'string') return err;
  if (err instanceof Error) return err.message;
  if (err && typeof err === 'object' && 'detail' in err) return String((err as any).detail);
  return 'Unknown error';
}

/** Mirrors backend `_auto_title_from` — keep slash commands intact. */
function autoTitleFrom(text: string, maxLen = 50): string {
  const cleaned = text.trim().split('\n')[0].trim();
  if (!cleaned) return 'New chat';
  return cleaned.length > maxLen ? cleaned.slice(0, maxLen - 1).trimEnd() + '…' : cleaned;
}

const EXAMPLE_PROMPTS: Array<{ label: string; text: string }> = [
  { label: 'Quick log', text: 'Log my breakfast: 2 scrambled eggs, toast and a black coffee' },
  { label: "Today's totals", text: '/macros' },
  { label: 'Recipe ideas', text: 'Suggest a high-protein vegetarian dinner under 700 kcal' },
  { label: 'Photo analysis', text: 'Analyse this photo of my lunch and tell me the macros' },
  { label: 'Weekly check-in', text: '/weekly' },
  { label: 'Plan tomorrow', text: 'Plan three meals for tomorrow that hit my goal' },
];

export function ChatView() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const params = useParams<{ sessionId?: string }>();
  // URL is the source of truth — derive selectedId directly, no syncing useState/effect.
  const selectedId = params.sessionId ? Number(params.sessionId) : null;

  const [pendingUserText, setPendingUserText] = useState<string | null>(null);
  const [pendingImagePath, setPendingImagePath] = useState<string | null>(null);
  const [pendingImagePreviewUrl, setPendingImagePreviewUrl] = useState<string | null>(null);
  const [prefill, setPrefill] = useState<string | null>(null);
  const { draft, send, seedThinking, stop, clearDraft } = useStreamingChat();
  // pendingImagePath is read indirectly via the optimistic cache write below.
  void pendingImagePath;

  // Surface streamed errors as toasts so the user sees model failures (rate limit, 503, etc).
  const lastErrorRef = useRef<string>('');
  useEffect(() => {
    if (draft?.phase === 'error' && draft.error && draft.error !== lastErrorRef.current) {
      lastErrorRef.current = draft.error;
      toast.error(formatError(draft.error));
    }
    if (draft?.phase !== 'error' && lastErrorRef.current) lastErrorRef.current = '';
  }, [draft?.phase, draft?.error]);

  const displayName = useAuthStore((s) => s.displayName);
  const authReady = useAuthStore((s) => s.ready);
  const uid = useAuthStore((s) => s.uid);
  const chatSidebarCollapsed = useUiStore((s) => s.chatSidebarCollapsed);
  const toggleChatSidebar = useUiStore((s) => s.toggleChatSidebar);

  // Shared hook (also used by History tab); prefetched in AuthProvider on boot.
  const conversations = useConversations();
  const currentConversation = conversations.data?.find((c) => c.id === selectedId) ?? null;
  // Skip the marketing-y hero block for anyone who already has past chats — they don't need
  // the welcome copy every time they hit "New chat".
  const isReturningUser = (conversations.data?.length ?? 0) > 0;

  const messages = useQuery({
    queryKey: ['conversation', selectedId, 'messages'],
    queryFn: () => listMessages(selectedId!),
    // Wait for auth to be ready so the request goes out with a valid token.
    // Without this guard the query fires on page load before Firebase resolves the session.
    enabled: selectedId !== null && authReady && !!uid,
  });

  // Clicking "New chat" must be instant — no API round-trip. Navigate to `/`, and let
  // `ensureSession()` create the row lazily on first send. `/` itself stays as the empty
  // hero forever; we deliberately don't auto-redirect to the latest conversation.
  const handleNewChat = () => {
    clearDraft();
    setPendingUserText(null);
    setPendingImagePath(null);
    setPendingImagePreviewUrl(null);
    navigate('/');
  };

  const ensureSession = async (): Promise<number> => {
    if (selectedId !== null) return selectedId;
    const c = await createConversation();
    queryClient.setQueryData<Conversation[]>(['conversations'], (prev) => [c, ...(prev ?? [])]);
    // Push to URL so refresh keeps the conversation. `replace` so back button doesn't strand you.
    navigate(`/c/${c.id}`, { replace: true });
    return c.id;
  };

  const handleSend = async (text: string, file?: File | null) => {
    let imagePath: string | null = null;
    let composedText = text;
    let previewUrl: string | null = null;

    if (file) {
      previewUrl = URL.createObjectURL(file);
      // Show the user's message + an "Analyzing the photo…" thinking chip BEFORE the slow
      // /photo/scan request returns, so the user gets immediate feedback.
      if (!composedText.trim()) {
        composedText = 'What is in this photo? Estimate the nutrition and log it if helpful.';
      }
      setPendingUserText(composedText);
      setPendingImagePreviewUrl(previewUrl);
      const finishAnalysis = seedThinking('analyze_image_tool');
      try {
        const photo = await uploadPhoto(file, { commit: false });
        imagePath = photo.image_path;
        finishAnalysis();
      } catch (err) {
        URL.revokeObjectURL(previewUrl);
        finishAnalysis();
        toast.error('Photo analysis failed: ' + formatError(err));
        setPendingUserText(null);
        setPendingImagePreviewUrl(null);
        clearDraft();
        return;
      }
    }

    if (!composedText.trim() && !imagePath) return;

    const sid = await ensureSession();
    // pendingUserText + previewUrl were set earlier (before upload) so the user could see
    // the placeholder while Gemini Vision was working. Just make sure they're current.
    setPendingUserText(composedText);
    setPendingImagePath(imagePath);
    if (!pendingImagePreviewUrl && previewUrl) setPendingImagePreviewUrl(previewUrl);

    await send({
      sessionId: sid,
      content: composedText,
      imagePath,
      onSettled: ({ text: finalAssistant, phase }) => {
        // If the stream errored, leave the inline error on the draft bubble — DON'T write a
        // bogus empty assistant row to the cache. The user can hit Retry without a corpse.
        if (phase === 'error') {
          setPendingUserText(null);
          setPendingImagePath(null);
          if (previewUrl) setTimeout(() => URL.revokeObjectURL(previewUrl), 1000);
          setPendingImagePreviewUrl(null);
          return;
        }

        // Optimistic cache update: append the user + assistant turn directly so the page doesn't
        // unmount/refetch (which used to cause a visible flicker). The next genuine query (route
        // change, page reload) will replace this with the canonical server data. NB: `text` here
        // comes from the SendResult snapshot — reading `draft?.text` from this scope's closure
        // would be stale.
        queryClient.setQueryData<Message[]>(
          ['conversation', sid, 'messages'],
          (prev = []) => {
            // The messages query may have already fetched the user message from the DB
            // (the backend commits it before streaming starts), so only append it if
            // it's not already present — otherwise we'd show two identical user bubbles.
            const hasUserMsg = prev.some((m) => m.role === 'user' && m.content === composedText);
            const base = hasUserMsg
              ? prev
              : [
                  ...prev,
                  {
                    id: -Date.now(),
                    role: 'user' as const,
                    content: composedText,
                    image_path: imagePath,
                    created_at: new Date().toISOString(),
                  },
                ];
            return [
              ...base,
              {
                id: -Date.now() - 1,
                role: 'assistant' as const,
                content: finalAssistant,
                image_path: null,
                created_at: new Date().toISOString(),
              },
            ];
          },
        );
        // Don't refetch the sessions list — instead, optimistically update the local cache
        // with the same auto-title the backend computes (see chat.py::_auto_title_from). This
        // avoids a round-trip + stale-while-revalidate flash on every stream completion.
        queryClient.setQueryData<Conversation[]>(['conversations'], (prev = []) =>
          prev.map((c) =>
            c.id === sid && (c.title ?? '').trim().toLowerCase() === 'new chat'
              ? { ...c, title: autoTitleFrom(composedText) }
              : c,
          ),
        );
        setPendingUserText(null);
        setPendingImagePath(null);
        if (previewUrl) {
          // The bubble image now points at the backend URL (built from `image_path`); release blob.
          setTimeout(() => URL.revokeObjectURL(previewUrl), 1000);
        }
        setPendingImagePreviewUrl(null);
        clearDraft();
      },
    });
  };

  const hasMessages = (messages.data?.length ?? 0) > 0 || pendingUserText !== null || draft !== null;
  // A selected session with no cached messages yet — show pulsing skeleton bubbles instead of
  // either the empty hero (misleading) or a blank screen.
  // But never show the skeleton while streaming: the draft/pendingUserText are the real content.
  const cachedCount = (messages.data ?? []).length;
  const isLoadingSelected =
    selectedId !== null &&
    messages.isLoading &&
    cachedCount === 0 &&
    draft === null &&
    pendingUserText === null;

  return (
    <div className="flex h-full">
      {!chatSidebarCollapsed && (
        <ConversationSidebar
          conversations={conversations.data ?? []}
          selectedId={selectedId}
          onSelect={(id) => {
            navigate(`/c/${id}`);
            clearDraft();
            setPendingUserText(null);
          }}
          onNew={handleNewChat}
        />
      )}
      <div className="flex flex-1 flex-col">
        <div className="flex items-center gap-2 border-b px-3 py-2">
          <Button variant="ghost" size="icon" onClick={toggleChatSidebar} title="Toggle conversations">
            {chatSidebarCollapsed ? (
              <PanelLeftOpen className="h-4 w-4" />
            ) : (
              <PanelLeftClose className="h-4 w-4" />
            )}
          </Button>
          <span className="truncate text-sm font-medium" title={currentConversation?.title}>
            {selectedId
              ? ((currentConversation?.title ?? '').trim() || 'Untitled chat')
              : 'New chat'}
          </span>
        </div>

        {isLoadingSelected ? (
          <>
            <MessageListSkeleton />
            <Composer disabled isStreaming={false} onSend={handleSend} onStop={stop} />
          </>
        ) : hasMessages ? (
          <>
            <MessageList
              messages={(messages.data ?? []) as Message[]}
              draft={draft}
              pendingUserText={pendingUserText}
              pendingImagePreviewUrl={pendingImagePreviewUrl}
            />
            <Composer
              disabled={false}
              isStreaming={draft != null && draft.phase !== 'done' && draft.phase !== 'error'}
              onSend={handleSend}
              onStop={stop}
            />
          </>
        ) : (
          <div className="flex flex-1 flex-col items-center justify-center px-6">
            {isReturningUser ? (
              // Tight empty state for users who already have past chats — no marketing-y hero,
              // just a friendly "ready when you are" + composer + a couple of suggestion chips.
              <>
                <p className="mb-4 text-sm text-muted-foreground">
                  {displayName
                    ? `Welcome back, ${displayName.split(' ')[0]}. What would you like to track today?`
                    : 'Ready when you are.'}
                </p>
                <div className="w-full max-w-2xl">
                  <Composer
                    disabled={false}
                    isStreaming={false}
                    onSend={handleSend}
                    onStop={stop}
                    prefill={prefill}
                    onPrefillConsumed={() => setPrefill(null)}
                  />
                </div>
                <div className="mt-4 flex w-full max-w-2xl flex-wrap justify-center gap-2">
                  {EXAMPLE_PROMPTS.slice(0, 4).map((p) => (
                    <button
                      key={p.text}
                      type="button"
                      onClick={() => setPrefill(p.text)}
                      className="rounded-full border bg-card px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:border-primary hover:text-foreground"
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </>
            ) : (
              <>
                <div className="mb-6 flex flex-col items-center gap-3 text-center">
                  <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-md">
                    <Dumbbell className="h-7 w-7" />
                  </div>
                  <h1 className="text-2xl font-semibold tracking-tight">
                    {displayName ? `Hi, ${displayName.split(' ')[0]}` : t('app.name')}
                  </h1>
                  <p className="max-w-md text-base text-muted-foreground">
                    Ask the agent to log a meal, plan your week, or analyse a photo. Tap a
                    suggestion below or just type freely.
                  </p>
                </div>
                <div className="w-full max-w-2xl">
                  <Composer
                    disabled={false}
                    isStreaming={false}
                    onSend={handleSend}
                    onStop={stop}
                    prefill={prefill}
                    onPrefillConsumed={() => setPrefill(null)}
                  />
                </div>
                <div className="mt-6 grid w-full max-w-2xl grid-cols-1 gap-2 sm:grid-cols-2">
                  {EXAMPLE_PROMPTS.map((p) => (
                    <button
                      key={p.text}
                      type="button"
                      onClick={() => setPrefill(p.text)}
                      className="group flex flex-col gap-1 rounded-xl border bg-card px-4 py-3 text-start transition-colors hover:border-primary hover:bg-accent/40"
                    >
                      <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground group-hover:text-accent-foreground">
                        {p.label}
                      </span>
                      <span className="text-sm">{p.text}</span>
                    </button>
                  ))}
                </div>
                <Sparkles className="mt-6 h-4 w-4 text-muted-foreground/50" />
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
