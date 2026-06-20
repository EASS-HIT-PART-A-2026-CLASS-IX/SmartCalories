import { useCallback, useRef, useState } from 'react';

import { streamChat, type StreamEvent } from '@/lib/api/chat';

export type StreamPhase = 'idle' | 'starting' | 'thinking' | 'tool_running' | 'streaming' | 'done' | 'error';

export interface ToolEvent {
  id: string;
  name: string;
  state: 'running' | 'done';
  argsPreview?: string;
  summary?: string;
}

export interface DraftMessage {
  id: string;
  text: string;
  tools: ToolEvent[];
  phase: StreamPhase;
  error?: string;
}

/** Snapshot of what the stream ultimately produced — passed to `onSettled`. Reading these
 *  via React state from the consumer doesn't work because closures capture stale values; the
 *  callback receives them directly so the optimistic cache write has the real text. */
export interface SendResult {
  text: string;
  toolNames: string[];
  phase: StreamPhase;
  error?: string;
}

interface SendOptions {
  sessionId: number;
  content: string;
  imagePath?: string | null;
  onSettled?: (result: SendResult) => void;
}

const newId = () => Math.random().toString(36).slice(2, 10);

export function useStreamingChat() {
  const [draft, setDraft] = useState<DraftMessage | null>(null);
  // Mirror of `draft` so async callbacks can read the latest value without React closure staleness.
  const draftRef = useRef<DraftMessage | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const updateDraft = useCallback(
    (next: DraftMessage | null | ((prev: DraftMessage | null) => DraftMessage | null)) => {
      setDraft((prev) => {
        const value = typeof next === 'function' ? next(prev) : next;
        draftRef.current = value;
        return value;
      });
    },
    [],
  );

  const send = useCallback(async ({ sessionId, content, imagePath, onSettled }: SendOptions) => {
    const controller = new AbortController();
    abortRef.current = controller;
    // Hard ceiling so a stuck Gemini call can't hang the bubble forever. 60s is well beyond
    // a normal multi-tool turn but short enough that the user sees a real error rather than
    // a silent spinner. Cleared on first event arrival.
    let timeoutId: ReturnType<typeof setTimeout> | null = setTimeout(() => {
      controller.abort('timeout');
    }, 60_000);
    const clearTimeoutOnce = () => {
      if (timeoutId !== null) {
        clearTimeout(timeoutId);
        timeoutId = null;
      }
    };

    // Preserve any tool chips that were seeded before the stream starts (e.g. the
    // "Analyzing the photo…" chip we set during multipart upload).
    updateDraft((prev) => ({
      id: prev?.id ?? newId(),
      text: prev?.text ?? '',
      tools: prev?.tools ?? [],
      phase: 'starting',
    }));

    try {
      await streamChat(sessionId, content, {
        imagePath,
        signal: controller.signal,
        onEvent: (event: StreamEvent) => {
          clearTimeoutOnce();
          updateDraft((prev) => prev && reduceDraft(prev, event));
        },
      });
    } catch (err) {
      const aborted = controller.signal.aborted;
      const reason = aborted && controller.signal.reason ? String(controller.signal.reason) : null;
      const message =
        reason === 'timeout'
          ? 'The agent took too long to respond (60 s). Try again.'
          : err instanceof Error
          ? err.message
          : 'Stream failed';
      updateDraft((prev) => (prev ? { ...prev, phase: 'error', error: message } : prev));
    } finally {
      clearTimeoutOnce();
      abortRef.current = null;
      const finalDraft = draftRef.current;
      onSettled?.({
        text: finalDraft?.text ?? '',
        toolNames: finalDraft?.tools.map((t) => t.name) ?? [],
        phase: finalDraft?.phase ?? 'done',
        error: finalDraft?.error,
      });
    }
  }, [updateDraft]);

  /**
   * Show a "thinking" tool chip BEFORE the SSE stream starts. Returns a `complete()` callback
   * that flips the chip to done. Useful for slow preflight work like multipart photo upload.
   */
  const seedThinking = useCallback(
    (toolName: string): (() => void) => {
      const tid = newId();
      updateDraft((prev) => ({
        id: prev?.id ?? newId(),
        text: prev?.text ?? '',
        tools: [...(prev?.tools ?? []), { id: tid, name: toolName, state: 'running' }],
        phase: 'tool_running',
      }));
      return () => {
        updateDraft((prev) =>
          prev
            ? {
                ...prev,
                tools: prev.tools.map((t) =>
                  t.id === tid ? { ...t, state: 'done' as const } : t,
                ),
              }
            : prev,
        );
      };
    },
    [updateDraft],
  );

  const stop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const clearDraft = useCallback(() => updateDraft(null), [updateDraft]);

  return { draft, send, seedThinking, stop, clearDraft };
}

function reduceDraft(prev: DraftMessage, event: StreamEvent): DraftMessage {
  switch (event.type) {
    case 'start':
      return { ...prev, phase: prev.phase === 'tool_running' ? prev.phase : 'thinking' };
    case 'thinking':
      return { ...prev, phase: prev.phase === 'tool_running' ? prev.phase : 'thinking' };
    case 'tool_call': {
      const name = String(event.data.name ?? 'tool');
      const argsPreview = event.data.args_preview as string | undefined;
      const tools = upsertTool(prev.tools, name, { state: 'running', argsPreview });
      return { ...prev, phase: 'tool_running', tools };
    }
    case 'tool_result': {
      const name = String(event.data.name ?? 'tool');
      const summary = event.data.summary as string | undefined;
      const tools = upsertTool(prev.tools, name, { state: 'done', summary });
      return { ...prev, phase: 'streaming', tools };
    }
    case 'token': {
      const delta = String(event.data.delta ?? '');
      return { ...prev, phase: 'streaming', text: prev.text + delta };
    }
    case 'error':
      return { ...prev, phase: 'error', error: String(event.data.message ?? 'error') };
    case 'done': {
      const text = (event.data.text as string | undefined) ?? prev.text;
      return { ...prev, phase: 'done', text };
    }
    default:
      return prev;
  }
}

function upsertTool(
  tools: ToolEvent[],
  name: string,
  patch: Partial<Omit<ToolEvent, 'id' | 'name'>>,
): ToolEvent[] {
  const idx = tools.findIndex((t) => t.name === name && t.state === 'running');
  if (idx === -1) {
    return [...tools, { id: newId(), name, state: 'running', ...patch }];
  }
  const next = [...tools];
  next[idx] = { ...next[idx], ...patch };
  return next;
}
