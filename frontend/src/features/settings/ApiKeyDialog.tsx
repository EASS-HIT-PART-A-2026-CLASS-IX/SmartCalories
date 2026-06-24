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

interface ProviderInfo {
  name: string;
  placeholder: string;
  consoleUrl: string;
  consoleLabel: string;
  note: string;
}

const ANTHROPIC: ProviderInfo = {
  name: 'Anthropic (Claude)',
  placeholder: 'sk-ant-…',
  consoleUrl: 'https://console.anthropic.com/settings/keys',
  consoleLabel: 'Open Anthropic Console',
  note: 'Paid — no free tier, but highest quality. Tried first when set.',
};

const GEMINI: ProviderInfo = {
  name: 'Google Gemini',
  placeholder: 'AIza…',
  consoleUrl: 'https://aistudio.google.com/apikey',
  consoleLabel: 'Open Google AI Studio',
  note: 'Has a free tier. Also powers meal-photo analysis.',
};

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
          <p className="text-sm text-muted-foreground">
            The app shares a free quota across everyone, so it can hit rate limits. Add your own
            key for <strong>Anthropic (Claude)</strong> and/or <strong>Gemini</strong> and your
            chats use it first — Claude before Gemini before the shared models. Keys are stored{' '}
            <strong>encrypted</strong> and only ever used for your messages.
          </p>

          {status.isLoading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Checking…
            </div>
          ) : (
            <>
              <ProviderKeySection
                info={ANTHROPIC}
                hasKey={!!s?.has_anthropic}
                last4={s?.anthropic_last4 ?? null}
                onSave={(k) => mutate.mutateAsync({ anthropic_api_key: k })}
                onClear={() => mutate.mutateAsync({ anthropic_api_key: '' })}
              />
              <ProviderKeySection
                info={GEMINI}
                hasKey={!!s?.has_gemini}
                last4={s?.gemini_last4 ?? null}
                onSave={(k) => mutate.mutateAsync({ gemini_api_key: k })}
                onClear={() => mutate.mutateAsync({ gemini_api_key: '' })}
              />
            </>
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
