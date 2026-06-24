import { api } from './client';

export interface LlmKeyStatus {
  has_key: boolean;
  gemini_last4: string | null;
}

export async function getLlmKey(): Promise<LlmKeyStatus> {
  return api<LlmKeyStatus>('/me/llm-key');
}

export async function setLlmKey(geminiApiKey: string): Promise<LlmKeyStatus> {
  return api<LlmKeyStatus>('/me/llm-key', {
    method: 'PUT',
    json: { gemini_api_key: geminiApiKey },
  });
}

export async function deleteLlmKey(): Promise<LlmKeyStatus> {
  return api<LlmKeyStatus>('/me/llm-key', { method: 'DELETE' });
}
