import { api } from './client';

export interface LlmKeyStatus {
  has_gemini: boolean;
  gemini_last4: string | null;
  has_anthropic: boolean;
  anthropic_last4: string | null;
}

/** For each provider: a non-empty string sets the key, '' clears it, undefined leaves unchanged. */
export interface LlmKeyUpdate {
  gemini_api_key?: string | null;
  anthropic_api_key?: string | null;
}

export async function getLlmKey(): Promise<LlmKeyStatus> {
  return api<LlmKeyStatus>('/me/llm-key');
}

export async function setLlmKey(update: LlmKeyUpdate): Promise<LlmKeyStatus> {
  return api<LlmKeyStatus>('/me/llm-key', { method: 'PUT', json: update });
}

/** Clears BOTH stored keys. */
export async function deleteLlmKey(): Promise<LlmKeyStatus> {
  return api<LlmKeyStatus>('/me/llm-key', { method: 'DELETE' });
}
