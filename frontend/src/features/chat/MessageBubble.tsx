import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useTranslation } from 'react-i18next';
import { Check, ChevronDown, ChevronRight, Copy, Dumbbell, Loader2 } from 'lucide-react';

import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { useAuthStore } from '@/stores/authStore';
import { env } from '@/lib/env';
import type { DraftMessage } from './useStreamingChat';

const TOOL_LABEL_KEY: Record<string, string> = {
  log_food: 'tools.logging',
  get_macros_today: 'tools.checking_macros',
  get_remaining_budget: 'tools.checking_budget',
  add_water: 'tools.logging_water',
  set_goal: 'tools.updating_goal',
  get_user_goals: 'tools.checking_goal',
  compute_tdee: 'tools.computing_tdee',
  analyze_image_tool: 'tools.analyzing_photo',
  get_streak: 'tools.checking_streak',
};

const StreamingCursor = () => (
  <span className="ms-0.5 inline-block h-3 w-2 translate-y-0.5 animate-pulse-soft bg-foreground" />
);

export interface BubbleProps {
  role: 'user' | 'assistant';
  text: string;
  imagePath?: string | null;
  imagePreviewUrl?: string | null;
  draft?: DraftMessage | null;
}

function buildImageUrl(
  imagePath: string | null | undefined,
  uid: string | null,
  token: string | null,
): string | null {
  if (!imagePath || !uid) return null;
  const marker = `uploads/${uid}/`;
  const idx = imagePath.indexOf(marker);
  if (idx === -1) return null;
  const tail = imagePath.slice(idx + marker.length);
  const url = new URL(`${env.apiBase}/uploads/${uid}/${tail}`);
  // <img> can't send Authorization headers — use the backend's `?token=` query fallback.
  if (token) url.searchParams.set('token', token);
  return url.toString();
}

export function MessageBubble({ role, text, draft, imagePath, imagePreviewUrl }: BubbleProps) {
  const isUser = role === 'user';
  const isStreaming = draft && draft.phase !== 'done' && draft.phase !== 'error';
  // Show the spinner whenever we're mid-stream with no text yet — covers starting, thinking,
  // tool_running, and early streaming before the first token arrives.
  const showThinking = !!isStreaming && !text;
  const uid = useAuthStore((s) => s.uid);
  const idToken = useAuthStore((s) => s.idToken);

  const imageUrl = imagePreviewUrl ?? buildImageUrl(imagePath, uid, idToken);

  // Empty assistant body once the stream is done is a model glitch (Gemini occasionally
  // ends a tool-using turn with no text). Surface a clear fallback instead of an empty bubble.
  const isEmptyDoneAssistant =
    !isUser && draft?.phase === 'done' && !text.trim() && (draft?.tools.length ?? 0) > 0;

  return (
    <div
      className={cn(
        'flex items-start gap-3 px-4 py-3',
        isUser ? 'justify-end' : 'justify-start',
      )}
    >
      {!isUser && (
        <div className="flex h-9 w-9 shrink-0 items-center justify-center self-start rounded-full bg-primary text-primary-foreground shadow">
          <Dumbbell className="h-4.5 w-4.5" />
        </div>
      )}
      <div className={cn('max-w-[78ch] space-y-2', isUser && 'order-1')}>
        {!isUser && draft && <ToolStrip draft={draft} />}
        {imageUrl && (
          <div className={cn('flex', isUser ? 'justify-end' : 'justify-start')}>
            <img
              src={imageUrl}
              alt="Uploaded"
              className="max-h-72 max-w-[18rem] rounded-xl border object-cover shadow-sm"
            />
          </div>
        )}
        <div
          className={cn(
            'rounded-2xl px-4 py-3 leading-relaxed shadow-sm',
            isUser ? 'bg-primary text-primary-foreground' : 'bg-card text-card-foreground border',
          )}
        >
          {showThinking && !text ? (
            <span className="inline-flex items-center gap-2 text-foreground/70">
              <Loader2 className="h-4 w-4 animate-spin text-primary" /> Thinking…
            </span>
          ) : isEmptyDoneAssistant ? (
            <span className="text-sm italic text-muted-foreground">
              The agent finished without a response. Try rephrasing or sending again.
            </span>
          ) : (
            <div className="prose prose-base dark:prose-invert max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
              {isStreaming && <StreamingCursor />}
            </div>
          )}
        </div>
        {!isUser && !isStreaming && text && <CopyAction text={text} />}
        {draft?.phase === 'error' && (
          <div className="mt-1 flex items-center gap-1.5 text-xs text-destructive">
            <span>⚠</span> {draft.error ?? 'Stream failed. Please try again.'}
          </div>
        )}
      </div>
    </div>
  );
}

function ToolStrip({ draft }: { draft: DraftMessage }) {
  const { t } = useTranslation();
  if (!draft.tools.length) return null;
  const label = (n: string) => (TOOL_LABEL_KEY[n] ? t(TOOL_LABEL_KEY[n]) : n.replace(/_/g, ' '));
  return (
    <div className="flex flex-wrap gap-2">
      {draft.tools.map((tool) => (
        <ToolChip
          key={tool.id}
          state={tool.state}
          label={label(tool.name)}
          summary={tool.summary}
        />
      ))}
    </div>
  );
}

function ToolChip({
  state,
  label,
  summary,
}: {
  state: 'running' | 'done';
  label: string;
  summary?: string;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-full border bg-secondary text-secondary-foreground text-xs">
      <button
        type="button"
        onClick={() => summary && setOpen(!open)}
        className="flex items-center gap-1.5 px-3 py-1"
      >
        {state === 'running' ? (
          <Loader2 className="h-3 w-3 animate-spin" />
        ) : (
          <Check className="h-3 w-3 text-primary" />
        )}
        <span>{label}</span>
        {summary ? (
          open ? (
            <ChevronDown className="h-3 w-3 opacity-60" />
          ) : (
            <ChevronRight className="h-3 w-3 opacity-60" />
          )
        ) : null}
      </button>
      {open && summary && (
        <pre className="max-w-md whitespace-pre-wrap break-all px-3 pb-2 text-[10px] text-muted-foreground">
          {summary}
        </pre>
      )}
    </div>
  );
}

function CopyAction({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={() => {
        void navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 1200);
      }}
      className="h-7 text-muted-foreground hover:text-foreground"
    >
      {copied ? <Check className="me-1 h-3 w-3" /> : <Copy className="me-1 h-3 w-3" />}
      {copied ? 'Copied' : 'Copy'}
    </Button>
  );
}
