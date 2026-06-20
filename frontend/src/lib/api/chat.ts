import { api } from './client';
import { env } from '../env';
import { getFirebaseAuth, refreshIdToken } from '../firebase';

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

export interface StreamEvent {
  type: 'start' | 'thinking' | 'tool_call' | 'tool_result' | 'token' | 'error' | 'done';
  data: Record<string, unknown>;
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

export async function deleteConversation(sessionId: number): Promise<void> {
  await api<void>(`/chat/sessions/${sessionId}`, { method: 'DELETE' });
}

async function getAuthHeader(): Promise<string | null> {
  const { useAuthStore } = await import('@/stores/authStore');
  const stored = useAuthStore.getState();
  if (stored.uid?.startsWith('demo-')) {
    return stored.idToken ? `Bearer ${stored.idToken}` : null;
  }
  const auth = getFirebaseAuth();
  if (auth?.currentUser) {
    return `Bearer ${await auth.currentUser.getIdToken()}`;
  }
  return stored.idToken ? `Bearer ${stored.idToken}` : null;
}

/** Open the SSE stream for a chat session. Calls onEvent for each typed event until done/error. */
export async function streamChat(
  sessionId: number,
  content: string,
  options: {
    imagePath?: string | null;
    signal?: AbortSignal;
    onEvent: (event: StreamEvent) => void;
  },
): Promise<void> {
  const url = `${env.apiBase}/chat/sessions/${sessionId}/stream`;
  let token = await getAuthHeader();
  let resp = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      ...(token ? { Authorization: token } : {}),
    },
    body: JSON.stringify({ content, image_path: options.imagePath ?? null }),
    signal: options.signal,
  });
  if (resp.status === 401) {
    token = (await refreshIdToken()) ? `Bearer ${await refreshIdToken()}` : null;
    if (token) {
      resp = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
          Authorization: token,
        },
        body: JSON.stringify({ content, image_path: options.imagePath ?? null }),
        signal: options.signal,
      });
    }
  }
  if (!resp.ok || !resp.body) {
    throw new Error(`Stream failed: ${resp.status}`);
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let separatorIdx = buffer.indexOf('\n\n');
    while (separatorIdx !== -1) {
      const block = buffer.slice(0, separatorIdx);
      buffer = buffer.slice(separatorIdx + 2);
      const event = parseSseBlock(block);
      if (event) options.onEvent(event);
      separatorIdx = buffer.indexOf('\n\n');
    }
  }
}

function parseSseBlock(block: string): StreamEvent | null {
  const lines = block.split('\n');
  let eventType: StreamEvent['type'] | null = null;
  const dataLines: string[] = [];
  for (const line of lines) {
    if (line.startsWith('event:')) eventType = line.slice(6).trim() as StreamEvent['type'];
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim());
  }
  if (!eventType) return null;
  let data: Record<string, unknown> = {};
  if (dataLines.length) {
    try {
      data = JSON.parse(dataLines.join('\n'));
    } catch {
      data = { raw: dataLines.join('\n') };
    }
  }
  return { type: eventType, data };
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
