import { api } from './client';

export interface LlmKeyStatus {
  has_anthropic: boolean;
  anthropic_last4: string | null;
  has_gemini: boolean;
  gemini_last4: string | null;
  has_groq: boolean;
  groq_last4: string | null;
  has_openrouter: boolean;
  openrouter_last4: string | null;
}

/** For each provider: a non-empty string sets the key, '' clears it, undefined leaves unchanged. */
export interface LlmKeyUpdate {
  anthropic_api_key?: string | null;
  gemini_api_key?: string | null;
  groq_api_key?: string | null;
  openrouter_api_key?: string | null;
}

export async function getLlmKey(): Promise<LlmKeyStatus> {
  return api<LlmKeyStatus>('/me/llm-key');
}

export async function setLlmKey(update: LlmKeyUpdate): Promise<LlmKeyStatus> {
  return api<LlmKeyStatus>('/me/llm-key', { method: 'PUT', json: update });
}
