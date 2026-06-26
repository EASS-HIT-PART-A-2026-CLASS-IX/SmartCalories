import { useCallback, useRef, useState } from 'react';

import { chatWsUrl, type ChatWsEvent, type Message } from '@/lib/api/chat';
import { getAuthToken } from '@/lib/api/client';

export type StreamPhase = 'idle' | 'thinking' | 'done' | 'error';

export interface DraftMessage {
  id: string;
  text: string;
  phase: StreamPhase;
  /** Name of the tool the agent is currently running (drives the live "Thinking" label). */
  tool?: string;
  error?: string;
}

export interface SessionInfo {
  id: number;
  title: string;
  isNew: boolean;
  createdAt: string;
}

export interface SendResult {
  text: string;
  phase: StreamPhase;
  error?: string;
  session?: SessionInfo;
  assistantMessage?: Message;
}

interface SendOptions {
  /** Existing session id, or null to let the backend create one in the same request. */
  sessionId: number | null;
  content: string;
  onSettled?: (result: SendResult) => void;
}

const newId = () => Math.random().toString(36).slice(2, 10);

const thinkingDraft = (id = newId()): DraftMessage => ({ id, text: '', phase: 'thinking' });

export function useStreamingChat() {
  const [draft, setDraft] = useState<DraftMessage | null>(null);
  const draftRef = useRef<DraftMessage | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const manualStopRef = useRef(false);

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

  const send = useCallback(
    async ({ sessionId, content, onSettled }: SendOptions) => {
      manualStopRef.current = false;
      updateDraft((prev) => (prev ? { ...prev, phase: 'thinking' } : thinkingDraft()));

      let settled = false;
      let session: SessionInfo | undefined;
      let assistantMessage: Message | undefined;
      let errorMsg: string | undefined;

      await new Promise<void>((resolve) => {
        const finish = (phase: StreamPhase) => {
          if (settled) return;
          settled = true;
          onSettled?.({
            text: assistantMessage?.content ?? '',
            phase,
            error: errorMsg,
            session,
            assistantMessage,
          });
          resolve();
        };

        getAuthToken()
          .then((token) => {
            const ws = new WebSocket(chatWsUrl(token));
            wsRef.current = ws;

            ws.onopen = () =>
              ws.send(
                JSON.stringify({
                  session_id: sessionId,
                  content,
                }),
              );

            ws.onmessage = (e) => {
              let ev: ChatWsEvent;
              try {
                ev = JSON.parse(e.data);
              } catch {
                return;
              }
              switch (ev.type) {
                case 'session':
                  session = {
                    id: ev.session_id,
                    title: ev.session_title,
                    isNew: ev.is_new_session,
                    createdAt: ev.session_created_at,
                  };
                  break;
                case 'tool':
                  updateDraft((d) =>
                    d ? { ...d, phase: 'thinking', tool: ev.name } : { ...thinkingDraft(), tool: ev.name },
                  );
                  break;
                case 'message':
                  assistantMessage = ev.message;
                  updateDraft({
                    id: draftRef.current?.id ?? newId(),
                    text: ev.message.content,
                    phase: 'done',
                  });
                  break;
                case 'title':
                  // LLM-refined title arrives just before 'done'; fold it into the session info
                  // so onSettled writes the nice title into the conversations cache + header.
                  if (session) session = { ...session, title: ev.title };
                  break;
                case 'error':
                  errorMsg = ev.message;
                  updateDraft((d) =>
                    d
                      ? { ...d, phase: 'error', tool: undefined, error: ev.message }
                      : { ...thinkingDraft(), phase: 'error', error: ev.message },
                  );
                  finish('error');
                  ws.close();
                  break;
                case 'done':
                  finish('done');
                  ws.close();
                  break;
              }
            };

            ws.onerror = () => {
              if (!errorMsg) errorMsg = 'Connection problem — please try again.';
            };

            ws.onclose = () => {
              wsRef.current = null;
              if (settled) return;
              if (manualStopRef.current) {
                updateDraft(null);
                finish('idle');
                return;
              }
              // Closed before a clean done/error (e.g. server dropped the socket).
              const msg = errorMsg ?? 'The connection closed before the reply finished. Try again.';
              errorMsg = msg;
              updateDraft((d) => (d ? { ...d, phase: 'error', tool: undefined, error: msg } : d));
              finish('error');
            };
          })
          .catch(() => {
            errorMsg = 'Could not authenticate the chat connection. Please sign in again.';
            updateDraft((d) => (d ? { ...d, phase: 'error', error: errorMsg } : d));
            finish('error');
          });
      });
    },
    [updateDraft],
  );

  /** Pre-show the "Thinking…" bubble before the send call, for immediate feedback. */
  const seedThinking = useCallback((): (() => void) => {
    updateDraft((prev) => prev ?? thinkingDraft());
    return () => {};
  }, [updateDraft]);

  const stop = useCallback(() => {
    manualStopRef.current = true;
    wsRef.current?.close();
  }, []);

  const clearDraft = useCallback(() => updateDraft(null), [updateDraft]);

  return { draft, send, seedThinking, stop, clearDraft };
}
