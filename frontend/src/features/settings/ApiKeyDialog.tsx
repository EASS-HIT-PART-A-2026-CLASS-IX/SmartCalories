import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Check, ExternalLink, KeyRound, Loader2, Trash2, X } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  getLlmKey,
  setLlmKey,
  type LlmKeyStatus,
  type LlmKeyUpdate,
} from '@/lib/api/account';
import { ApiError } from '@/lib/api/client';

interface Props {
  open: boolean;
  onClose: () => void;
}

type ProviderField = 'anthropic' | 'gemini' | 'groq' | 'openrouter';

interface ProviderInfo {
  field: ProviderField;
  name: string;
  placeholder: string;
  consoleUrl: string;
  consoleLabel: string;
  note: string;
}

// Order mirrors the backend fallback chain: Anthropic → Gemini → Groq → OpenRouter.
const PROVIDERS: ProviderInfo[] = [
  {
    field: 'anthropic',
    name: 'Anthropic (Claude)',
    placeholder: 'sk-ant-…',
    consoleUrl: 'https://console.anthropic.com/settings/keys',
    consoleLabel: 'Open Anthropic Console',
    note: 'Paid — no free tier, but highest quality. Tried first when set.',
  },
  {
    field: 'gemini',
    name: 'Google Gemini',
    placeholder: 'AIza…',
    consoleUrl: 'https://aistudio.google.com/apikey',
    consoleLabel: 'Open Google AI Studio',
    note: 'Generous free tier.',
  },
  {
    field: 'groq',
    name: 'Groq',
    placeholder: 'gsk_…',
    consoleUrl: 'https://console.groq.com/keys',
    consoleLabel: 'Open Groq Console',
    note: 'Free, very fast (Llama 3.3 70B + Gemma 2).',
  },
  {
    field: 'openrouter',
    name: 'OpenRouter',
    placeholder: 'sk-or-…',
    consoleUrl: 'https://openrouter.ai/keys',
    consoleLabel: 'Open OpenRouter',
    note: 'Free `:free` Llama/Gemma builds with strict daily caps.',
  },
];

const hasKeyFor = (s: LlmKeyStatus | undefined, field: ProviderField): boolean =>
  !!s?.[`has_${field}` as keyof LlmKeyStatus];

const last4For = (s: LlmKeyStatus | undefined, field: ProviderField): string | null =>
  (s?.[`${field}_last4` as keyof LlmKeyStatus] as string | null) ?? null;

export function ApiKeyDialog({ open, onClose }: Props) {
  const queryClient = useQueryClient();

  const status = useQuery({
    queryKey: ['llm-key'],
    queryFn: getLlmKey,
    enabled: open,
    staleTime: 60_000,
  });

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  const mutate = useMutation({
    mutationFn: (u: LlmKeyUpdate) => setLlmKey(u),
    onSuccess: (data) => queryClient.setQueryData<LlmKeyStatus>(['llm-key'], data),
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.detail : 'Could not update the key.'),
  });

  if (!open) return null;

  const s = status.data;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
    >
      <div
        className="flex max-h-[90dvh] w-full max-w-lg flex-col overflow-hidden rounded-2xl border bg-card text-card-foreground shadow-xl"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="flex items-center gap-2 border-b px-5 py-4">
          <KeyRound className="h-5 w-5 text-primary" />
          <h2 className="flex-1 text-lg font-semibold">Use your own API keys</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-5 overflow-y-auto px-5 py-5">
          <div className="space-y-3 text-sm text-muted-foreground">
            <p>
              The app shares a free quota across everyone, so it can hit rate limits. Add your own
              key for any of the providers below and your chats use <strong>your</strong> keys
              first. Keys are stored <strong>encrypted</strong> and only ever used for your
              messages.
            </p>
            <div className="rounded-lg border bg-background/40 p-3">
              <p className="mb-1.5 font-medium text-foreground">How fallback works</p>
              <p className="mb-2">
                The agent tries providers in order and moves to the next one whenever a model is
                rate-limited or errors — so a single busy provider never blocks your chat:
              </p>
              <ol className="list-inside list-decimal space-y-0.5">
                <li>
                  <strong>Anthropic (Claude)</strong> — highest quality
                </li>
                <li>
                  <strong>Gemini</strong>
                </li>
                <li>
                  <strong>Groq</strong>
                </li>
                <li>
                  <strong>OpenRouter</strong>
                </li>
                <li>the app's shared free pool (last resort)</li>
              </ol>
              <p className="mt-2">
                Your own keys are always tried before the shared pool, in this same order. We
                recommend adding keys <strong>in this fallback order</strong> — start with the ones
                you have, and add more for extra resilience.
              </p>
            </div>
          </div>

          {status.isLoading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Checking…
            </div>
          ) : (
            PROVIDERS.map((info) => (
              <ProviderKeySection
                key={info.field}
                info={info}
                hasKey={hasKeyFor(s, info.field)}
                last4={last4For(s, info.field)}
                onSave={(k) =>
                  mutate.mutateAsync({ [`${info.field}_api_key`]: k } as LlmKeyUpdate)
                }
                onClear={() =>
                  mutate.mutateAsync({ [`${info.field}_api_key`]: '' } as LlmKeyUpdate)
                }
              />
            ))
          )}
        </div>
      </div>
    </div>
  );
}

function ProviderKeySection({
  info,
  hasKey,
  last4,
  onSave,
  onClear,
}: {
  info: ProviderInfo;
  hasKey: boolean;
  last4: string | null;
  onSave: (key: string) => Promise<unknown>;
  onClear: () => Promise<unknown>;
}) {
  const [value, setValue] = useState('');
  const [busy, setBusy] = useState(false);

  const doSave = async () => {
    const k = value.trim();
    if (!k || busy) return;
    setBusy(true);
    try {
      await onSave(k);
      setValue('');
      toast.success(`${info.name} key saved.`);
    } catch {
      /* mutation's onError already toasted */
    } finally {
      setBusy(false);
    }
  };

  const doClear = async () => {
    if (busy) return;
    setBusy(true);
    try {
      await onClear();
      toast.success(`Removed your ${info.name} key.`);
    } catch {
      /* handled by onError */
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-2 rounded-lg border bg-background/40 p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">{info.name}</h3>
        {hasKey && (
          <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Check className="h-3.5 w-3.5 text-primary" />
            saved <span className="font-mono">••••{last4}</span>
          </span>
        )}
      </div>
      <p className="text-xs text-muted-foreground">{info.note}</p>
      <div className="flex gap-2">
        <Input
          type="password"
          autoComplete="off"
          placeholder={hasKey ? 'Replace with a new key…' : info.placeholder}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && void doSave()}
          disabled={busy}
        />
        <Button onClick={() => void doSave()} disabled={busy || !value.trim()}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Save'}
        </Button>
        {hasKey && (
          <Button
            variant="ghost"
            size="icon"
            onClick={() => void doClear()}
            disabled={busy}
            title={`Remove ${info.name} key`}
            className="text-destructive hover:text-destructive"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        )}
      </div>
      <a
        href={info.consoleUrl}
        target="_blank"
        rel="noreferrer"
        className="inline-flex items-center gap-1.5 text-xs font-medium text-primary hover:underline"
      >
        {info.consoleLabel} <ExternalLink className="h-3 w-3" />
      </a>
    </div>
  );
}
