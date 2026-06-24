import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Check, ExternalLink, KeyRound, Loader2, Trash2, X } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { deleteLlmKey, getLlmKey, setLlmKey, type LlmKeyStatus } from '@/lib/api/account';
import { ApiError } from '@/lib/api/client';

const AI_STUDIO_URL = 'https://aistudio.google.com/apikey';

const STEPS: string[] = [
  'Open Google AI Studio (link below) and sign in with your Google account.',
  'Click "Create API key", then "Create API key in new project".',
  'Copy the generated key — it starts with "AIza".',
  'Paste it below and save. It\'s stored encrypted and used only for your chats.',
];

interface Props {
  open: boolean;
  onClose: () => void;
}

export function ApiKeyDialog({ open, onClose }: Props) {
  const queryClient = useQueryClient();
  const [value, setValue] = useState('');

  const status = useQuery({
    queryKey: ['llm-key'],
    queryFn: getLlmKey,
    enabled: open,
    staleTime: 60_000,
  });

  // Close on Escape for keyboard users.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  const save = useMutation({
    mutationFn: (key: string) => setLlmKey(key),
    onSuccess: (data) => {
      queryClient.setQueryData<LlmKeyStatus>(['llm-key'], data);
      setValue('');
      toast.success('Gemini API key saved — your chats will use it.');
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.detail : 'Could not save the key.'),
  });

  const remove = useMutation({
    mutationFn: deleteLlmKey,
    onSuccess: (data) => {
      queryClient.setQueryData<LlmKeyStatus>(['llm-key'], data);
      toast.success('Removed your key — back to the shared models.');
    },
    onError: () => toast.error('Could not remove the key.'),
  });

  if (!open) return null;

  const hasKey = status.data?.has_key;
  const last4 = status.data?.gemini_last4;
  const busy = save.isPending || remove.isPending;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg overflow-hidden rounded-2xl border bg-card text-card-foreground shadow-xl"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="flex items-center gap-2 border-b px-5 py-4">
          <KeyRound className="h-5 w-5 text-primary" />
          <h2 className="flex-1 text-lg font-semibold">Use your own Gemini API key</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-5 px-5 py-5">
          <p className="text-sm text-muted-foreground">
            The app shares a free Gemini quota across everyone, so it can hit rate limits. Add your
            own free key and your chats will use it first — no more waiting on the shared limit.
            Your key is stored <strong>encrypted</strong> and only ever used for your messages.
          </p>

          {/* Current status */}
          {status.isLoading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Checking…
            </div>
          ) : hasKey ? (
            <div className="flex items-center justify-between rounded-lg border bg-secondary/50 px-3 py-2 text-sm">
              <span className="flex items-center gap-2">
                <Check className="h-4 w-4 text-primary" />
                Key saved <span className="font-mono text-muted-foreground">••••{last4}</span>
              </span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => remove.mutate()}
                disabled={busy}
                className="text-destructive hover:text-destructive"
              >
                <Trash2 className="me-1 h-3.5 w-3.5" />
                Remove
              </Button>
            </div>
          ) : null}

          {/* Input + save */}
          <div className="space-y-2">
            <label className="text-sm font-medium">
              {hasKey ? 'Replace with a new key' : 'Paste your Gemini API key'}
            </label>
            <div className="flex gap-2">
              <Input
                type="password"
                autoComplete="off"
                placeholder="AIza…"
                value={value}
                onChange={(e) => setValue(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && value.trim() && save.mutate(value.trim())}
              />
              <Button onClick={() => save.mutate(value.trim())} disabled={busy || !value.trim()}>
                {save.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Save'}
              </Button>
            </div>
          </div>

          {/* How to generate */}
          <div className="rounded-lg border bg-background/50 p-4">
            <h3 className="mb-2 text-sm font-semibold">How to get a key (free, ~1 minute)</h3>
            <ol className="space-y-1.5 text-sm text-muted-foreground">
              {STEPS.map((step, i) => (
                <li key={i} className="flex gap-2">
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/15 text-xs font-medium text-primary">
                    {i + 1}
                  </span>
                  <span>{step}</span>
                </li>
              ))}
            </ol>
            <a
              href={AI_STUDIO_URL}
              target="_blank"
              rel="noreferrer"
              className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline"
            >
              Open Google AI Studio <ExternalLink className="h-3.5 w-3.5" />
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
