import { api } from './client';
import { env } from '../env';

/** Build the chat WebSocket URL from the configured API base (http→ws), with the auth token. */
export function chatWsUrl(token: string | null): string {
  const base = env.apiBase
    ? env.apiBase.replace(/^http/, 'ws')
    : `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}`;
  const qs = token ? `?token=${encodeURIComponent(token)}` : '';
  return `${base}/chat/ws${qs}`;
}

/** A single event pushed from the chat WebSocket. */
export type ChatWsEvent =
  | { type: 'session'; session_id: number; session_title: string; session_created_at: string; is_new_session: boolean }
  | { type: 'tool'; name: string }
  | { type: 'message'; message: Message }
  | { type: 'title'; session_id: number; title: string }
  | { type: 'error'; message: string }
  | { type: 'done' };

export interface Conversation {
  id: number;
  title: string;
  created_at: string;
}

export interface Message {
  id: number;
  role: 'user' | 'assistant' | 'tool';
  content: string;
  image_path: string | null;
  created_at: string;
}

/** Response of the unified create-or-append send endpoint. */
export interface SendMessageResult {
  session_id: number;
  session_title: string;
  session_created_at: string;
  is_new_session: boolean;
  message: Message;
}

export async function listConversations(): Promise<Conversation[]> {
  return api<Conversation[]>('/chat/sessions');
}

export async function createConversation(title = 'New chat'): Promise<Conversation> {
  return api<Conversation>('/chat/sessions', { method: 'POST', json: { title } });
}

export async function listMessages(sessionId: number): Promise<Message[]> {
  return api<Message[]>(`/chat/sessions/${sessionId}/messages`);
}

/** Search the user's chats by content (title + every message, both roles). Newest-first. */
export async function searchConversations(q: string): Promise<Conversation[]> {
  return api<Conversation[]>('/chat/sessions/search', { query: { q } });
}

export async function deleteConversation(sessionId: number): Promise<void> {
  await api<void>(`/chat/sessions/${sessionId}`, { method: 'DELETE' });
}

/**
 * Send a chat message in a single round-trip. Pass `sessionId: null` to lazily create a new
 * session as part of the same call — the backend returns the resolved session metadata plus
 * the assistant reply, so no separate "create session" request is needed.
 */
export async function sendMessage(
  content: string,
  opts: { sessionId?: number | null; imagePath?: string | null; signal?: AbortSignal } = {},
): Promise<SendMessageResult> {
  return api<SendMessageResult>('/chat/messages', {
    method: 'POST',
    json: { session_id: opts.sessionId ?? null, content, image_path: opts.imagePath ?? null },
    signal: opts.signal,
  });
}

export async function uploadPhoto(file: File, opts: { commit?: boolean; meal?: string } = {}): Promise<{
  image_path: string;
  extraction: {
    name: string;
    calories: number;
    protein_g: number;
    carb_g: number;
    fat_g: number;
    confidence: number;
    note?: string | null;
  };
  entry: { id: number; name: string; calories: number; meal: string } | null;
}> {
  const fd = new FormData();
  fd.append('file', file);
  const params = new URLSearchParams();
  if (opts.commit) params.set('commit', 'true');
  if (opts.meal) params.set('meal', opts.meal);
  return api(`/photo/scan?${params.toString()}`, {
    method: 'POST',
    body: fd,
  });
}
