import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Check, Copy, Dumbbell, Loader2 } from 'lucide-react';

import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import type { DraftMessage } from './useStreamingChat';

/** Friendly present-tense labels for the live "Thinking" indicator, keyed by tool name. */
const TOOL_LABELS: Record<string, string> = {
  log_food: 'Logging your food',
  list_recent_foods: 'Looking up your entries',
  update_food: 'Updating your entry',
  delete_food: 'Removing your entry',
  get_macros_today: 'Checking today’s macros',
  get_remaining_budget: 'Checking your budget',
  get_streak: 'Checking your streak',
  add_water: 'Logging water',
  get_user_goals: 'Checking your goals',
  set_goal: 'Updating your goals',
  compute_tdee: 'Crunching your TDEE',
  search_nutrition: 'Searching nutrition data',
  web_search: 'Searching the web',
};

function toolLabel(name?: string): string {
  if (!name) return 'Thinking…';
  return (TOOL_LABELS[name] ?? name.replace(/_/g, ' ')) + '…';
}

export interface BubbleProps {
  role: 'user' | 'assistant';
  text: string;
  model?: string | null;
  draft?: DraftMessage | null;
}

/** "anthropic/claude-3-5-haiku-latest" → "claude-3-5-haiku-latest"; "gemini/gemini-2.0-flash" →
 *  "gemini-2.0-flash". Drops the LiteLLM provider prefix for a compact attribution label. */
function prettyModel(model?: string | null): string | null {
  if (!model) return null;
  const slash = model.indexOf('/');
  return slash === -1 ? model : model.slice(slash + 1);
}

export function MessageBubble({ role, text, draft, model }: BubbleProps) {
  const isUser = role === 'user';
  const isPending = draft && draft.phase !== 'done' && draft.phase !== 'error';
  // Show the "Thinking…" spinner while the agent turn is in flight and no text has arrived yet.
  const showThinking = !!isPending && !text;

  // Empty assistant body once the turn is done is a model glitch (Gemini occasionally
  // ends a tool-using turn with no text). Surface a clear fallback instead of an empty bubble.
  const isEmptyDoneAssistant = !isUser && draft?.phase === 'done' && !text.trim();

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
      <div className={cn('max-w-[90ch] space-y-2', isUser && 'order-1')}>
        <div
          className={cn(
            'rounded-2xl px-4 py-3 leading-relaxed shadow-sm',
            isUser ? 'bg-primary text-primary-foreground' : 'bg-card text-card-foreground border',
          )}
        >
          {showThinking && !text ? (
            <span className="inline-flex items-center gap-2 text-foreground">
              <Loader2 className="h-4 w-4 animate-spin text-primary" /> {toolLabel(draft?.tool)}
            </span>
          ) : isEmptyDoneAssistant ? (
            <span className="text-sm italic text-muted-foreground">
              The agent finished without a response. Try rephrasing or sending again.
            </span>
          ) : isUser ? (
            // User text is what they typed — render verbatim (preserve line breaks) so prose's
            // body color doesn't override the colored bubble's text-primary-foreground.
            <div className="whitespace-pre-wrap break-words">{text}</div>
          ) : (
            // Assistant replies are markdown — render with GFM + Tailwind Typography. The
            // `prose-*` overrides tighten chat spacing and inherit the bubble's foreground color.
            <div
              className={cn(
                'prose prose-sm dark:prose-invert max-w-none break-words',
                'prose-p:my-2 prose-headings:mt-3 prose-headings:mb-2 prose-pre:my-2',
                'prose-ul:my-2 prose-ol:my-2 prose-li:my-0.5',
                'prose-pre:bg-muted prose-pre:text-foreground prose-code:before:content-none prose-code:after:content-none',
              )}
            >
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
            </div>
          )}
        </div>
        {!isUser && !isPending && text && (
          <div className="flex items-center gap-1">
            <CopyAction text={text} />
            {prettyModel(model) && (
              <span
                className="text-[10px] leading-none text-muted-foreground/70"
                title={model ?? undefined}
              >
                {prettyModel(model)}
              </span>
            )}
          </div>
        )}
        {draft?.phase === 'error' && (
          <div className="mt-1 flex items-center gap-1.5 text-xs text-destructive">
            <span>⚠</span> {draft.error ?? 'Stream failed. Please try again.'}
          </div>
        )}
      </div>
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
