import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Dumbbell, Sparkles } from 'lucide-react';

import {
  listMessages,
  uploadPhoto,
  type Conversation,
  type Message,
} from '@/lib/api/chat';
import { useAuthStore } from '@/stores/authStore';
import { useConversations } from '@/hooks/useConversations';
import { MessageList, MessageListSkeleton } from './MessageList';
import { Composer } from './Composer';
import { useStreamingChat } from './useStreamingChat';

function formatError(err: unknown): string {
  if (typeof err === 'string') return err;
  if (err instanceof Error) return err.message;
  if (err && typeof err === 'object' && 'detail' in err) return String((err as any).detail);
  return 'Unknown error';
}

const EXAMPLE_PROMPTS: Array<{ label: string; text: string }> = [
  { label: 'Quick log', text: 'Log my breakfast: 2 scrambled eggs, toast and a black coffee' },
  { label: "Today's totals", text: 'What are my macros today?' },
  { label: 'Recipe ideas', text: 'Suggest a high-protein vegetarian dinner under 700 kcal' },
  { label: 'Calories left', text: 'How many calories do I have left today?' },
  { label: 'Weekly check-in', text: 'How did I do this week?' },
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

  // Shared hook; prefetched in AuthProvider on boot. Also drives the sidebar "Recents" list.
  const conversations = useConversations();
  const currentConversation = conversations.data?.find((c) => c.id === selectedId) ?? null;
  // Skip the marketing-y hero block for anyone who already has past chats — they don't need
  // the welcome copy every time they hit "New chat".
  const isReturningUser = (conversations.data?.length ?? 0) > 0;

  // Returning-user greeting: pick one at random per mount so the empty state feels alive.
  const firstName = displayName?.split(' ')[0];
  const greetings = useMemo(
    () =>
      firstName
        ? [
            `Welcome back, ${firstName}.`,
            `Hey ${firstName} — what are we tracking today?`,
            `Good to see you, ${firstName}.`,
            `Ready when you are, ${firstName}.`,
            `Let's hit your goals today, ${firstName}.`,
            `What did you eat today, ${firstName}?`,
          ]
        : [
            'Ready when you are.',
            'What are we tracking today?',
            'Let’s log something delicious.',
            'What did you eat today?',
            'Good to see you.',
            'Let’s hit your goals today.',
          ],
    [firstName],
  );
  // Lazy initializer → stable across re-renders; re-randomizes only on a fresh mount.
  const [greetingSeed] = useState(() => Math.floor(Math.random() * 1_000_000));
  const greeting = greetings[greetingSeed % greetings.length];

  const messages = useQuery({
    queryKey: ['conversation', selectedId, 'messages'],
    queryFn: () => listMessages(selectedId!),
    // Guards, in order:
    // - selectedId !== null && selectedId > 0: skip the empty hero AND the optimistic temp
    //   session (negative id) that has no server row yet — fetching it would 404.
    // - authReady && uid: wait for Firebase so the request carries a valid token.
    // - pendingUserText === null: don't fetch while a send is in-flight; the optimistic cache
    //   write in onSettled is the source of truth until then.
    enabled:
      selectedId !== null && selectedId > 0 && authReady && !!uid && pendingUserText === null,
  });

  const handleSend = async (text: string, file?: File | null) => {
    let imagePath: string | null = null;
    let composedText = text;
    let previewUrl: string | null = null;

    if (file) {
      previewUrl = URL.createObjectURL(file);
      // Show the user's message + a "Thinking…" bubble BEFORE the slow /photo/scan request
      // returns, so the user gets immediate feedback.
      if (!composedText.trim()) {
        composedText = 'What is in this photo? Estimate the nutrition and log it if helpful.';
      }
      setPendingUserText(composedText);
      setPendingImagePreviewUrl(previewUrl);
      const finishAnalysis = seedThinking();
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

    // A brand-new chat has no session yet. The single send call below creates the real session
    // server-side; we DON'T navigate to a placeholder URL. Instead we render the chat in place
    // from the pending state (the view shows whenever pendingUserText/draft is set, regardless of
    // the URL), then navigate to /c/:realId once the backend returns the real id. This avoids the
    // remount that a navigate to a temp /c/:id triggers — which would drop the in-flight state and
    // bounce the user back to the hero until the request finished.
    const isNewChat = selectedId === null;
    const originSessionId = selectedId; // real id when continuing an existing chat, else null

    // Immediate feedback: show the user's bubble + a "Thinking…" agent bubble right away,
    // in this same component instance.
    setPendingUserText(composedText);
    setPendingImagePath(imagePath);
    if (previewUrl) setPendingImagePreviewUrl(previewUrl);
    seedThinking();

    await send({
      sessionId: originSessionId,
      content: composedText,
      imagePath,
      onSettled: (result) => {
        const releasePreview = () => {
          if (previewUrl) setTimeout(() => URL.revokeObjectURL(previewUrl), 1000);
        };

        if (result.phase === 'idle') {
          // User hit Stop — cancel cleanly: drop the pending message + thinking bubble entirely,
          // reverting to the prior state (cached messages for an existing chat, hero for a new one).
          setPendingUserText(null);
          setPendingImagePath(null);
          releasePreview();
          setPendingImagePreviewUrl(null);
          clearDraft();
          return;
        }

        if (result.phase === 'error' || !result.session || !result.assistantMessage) {
          // Keep pendingUserText + the error draft so the user still sees their message and the
          // inline error and can retry. We never navigated away, so there's nothing to roll back.
          setPendingImagePath(null);
          releasePreview();
          setPendingImagePreviewUrl(null);
          return;
        }

        const realId = result.session.id;

        // Write the canonical messages cache for the REAL session first (fresh data), so once
        // selectedId becomes realId the messages query is satisfied and never fires a GET.
        queryClient.setQueryData<Message[]>(['conversation', realId, 'messages'], (prev = []) => {
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
          return [...base, result.assistantMessage!];
        });

        // Reconcile the conversations list: for a new chat, prepend the real session (with its
        // auto-title) so it appears in the sidebar; for an existing chat, refresh the title.
        queryClient.setQueryData<Conversation[]>(['conversations'], (prev = []) =>
          isNewChat
            ? [
                {
                  id: realId,
                  title: result.session!.title,
                  created_at: result.session!.createdAt,
                },
                ...prev.filter((c) => c.id !== realId),
              ]
            : prev.map((c) => (c.id === realId ? { ...c, title: result.session!.title } : c)),
        );

        // Now move to the real session URL. The messages cache is already populated, so the
        // chat stays on screen seamlessly (no hero flash, no refetch).
        if (selectedId !== realId) navigate(`/c/${realId}`, { replace: isNewChat });

        setPendingUserText(null);
        setPendingImagePath(null);
        releasePreview();
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
      <div className="flex flex-1 flex-col">
        <div className="flex items-center gap-2 border-b px-3 py-2">
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
                <h1 className="mb-6 text-center text-2xl font-semibold tracking-tight md:text-3xl">
                  {greeting}
                </h1>
                <div className="w-full max-w-4xl">
                  <Composer
                    disabled={false}
                    isStreaming={false}
                    onSend={handleSend}
                    onStop={stop}
                    prefill={prefill}
                    onPrefillConsumed={() => setPrefill(null)}
                  />
                </div>
                <div className="mt-4 flex w-full max-w-4xl flex-wrap justify-center gap-2">
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
                <div className="w-full max-w-4xl">
                  <Composer
                    disabled={false}
                    isStreaming={false}
                    onSend={handleSend}
                    onStop={stop}
                    prefill={prefill}
                    onPrefillConsumed={() => setPrefill(null)}
                  />
                </div>
                <div className="mt-6 grid w-full max-w-4xl grid-cols-1 gap-2 sm:grid-cols-2">
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
