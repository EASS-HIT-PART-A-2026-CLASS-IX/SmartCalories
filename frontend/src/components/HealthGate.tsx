import { useCallback, useEffect, useRef, useState } from 'react';
import { Loader2, Sparkles, UtensilsCrossed } from 'lucide-react';

import { env } from '@/lib/env';
import { Button } from '@/components/ui/button';

/**
 * Gates the whole app on a backend health check. The deployed API runs on a free tier that
 * sleeps when idle, so the first request after a while triggers a cold start (~30–60s). Until
 * `/health` answers OK we show a welcoming "waking up" screen and keep retrying, rather than
 * letting the app load into a broken state.
 */

type Phase = 'checking' | 'waking' | 'ok';

const HEALTH_URL = `${env.apiBase}/health`;
const PING_TIMEOUT_MS = 5_000;
const RETRY_DELAY_MS = 3_000;

/**
 * Dev-only health mock so you can test the "waking up" UI locally without taking the backend
 * down. Append a query param (ignored entirely in production builds):
 *   ?mockHealth=down   → health never recovers (test the stuck screen + "Try again" button)
 *   ?mockHealth=15     → simulate a cold start that recovers after 15 seconds
 */
const MOCK_HEALTH =
  import.meta.env.DEV ? new URLSearchParams(window.location.search).get('mockHealth') : null;

export function HealthGate({ children }: { children: React.ReactNode }) {
  const [phase, setPhase] = useState<Phase>('checking');
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const startRef = useRef<number>(0);
  const cancelledRef = useRef(false);

  const ping = useCallback(async () => {
    // Dev-only mock: short-circuit the real request to exercise the gate UI locally.
    if (MOCK_HEALTH !== null) {
      const recoverAfter = Number(MOCK_HEALTH);
      const ok =
        MOCK_HEALTH !== 'down' &&
        !Number.isNaN(recoverAfter) &&
        Date.now() - startRef.current >= recoverAfter * 1_000;
      if (cancelledRef.current) return;
      if (ok) {
        setPhase('ok');
      } else {
        setPhase((p) => (p === 'ok' ? p : 'waking'));
        timerRef.current = setTimeout(ping, RETRY_DELAY_MS);
      }
      return;
    }

    const controller = new AbortController();
    const to = setTimeout(() => controller.abort(), PING_TIMEOUT_MS);
    let ok = false;
    try {
      const resp = await fetch(HEALTH_URL, { signal: controller.signal, cache: 'no-store' });
      ok = resp.ok;
    } catch {
      ok = false;
    } finally {
      clearTimeout(to);
    }
    if (cancelledRef.current) return;
    if (ok) {
      setPhase('ok');
    } else {
      // First failure flips us into the "waking up" explainer; subsequent failures just keep
      // retrying. Once we're in 'waking' we never go back so the copy doesn't flicker.
      setPhase((p) => (p === 'ok' ? p : 'waking'));
      timerRef.current = setTimeout(ping, RETRY_DELAY_MS);
    }
  }, []);

  const retryNow = useCallback(() => {
    clearTimeout(timerRef.current);
    void ping();
  }, [ping]);

  useEffect(() => {
    cancelledRef.current = false;
    startRef.current = Date.now();
    void ping();
    return () => {
      cancelledRef.current = true;
      clearTimeout(timerRef.current);
    };
  }, [ping]);

  // Tick the elapsed-seconds counter while we're waiting on a cold start.
  useEffect(() => {
    if (phase !== 'waking') return;
    const id = setInterval(
      () => setElapsed(Math.round((Date.now() - startRef.current) / 1000)),
      1_000,
    );
    return () => clearInterval(id);
  }, [phase]);

  if (phase === 'ok') return <>{children}</>;

  const isWaking = phase === 'waking';

  return (
    <div className="flex min-h-dvh items-center justify-center bg-background px-6 text-foreground">
      <div className="w-full max-w-md text-center">
        {/* Logo mark */}
        <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-lg">
          <UtensilsCrossed className="h-8 w-8" />
        </div>

        <h1 className="mb-3 flex items-center justify-center gap-2 text-2xl font-semibold tracking-tight">
          {isWaking ? 'Waking up SmartCalories' : 'Connecting…'}
          <Sparkles className="h-5 w-5 text-primary" />
        </h1>

        <p className="mx-auto mb-8 max-w-sm text-base leading-relaxed text-muted-foreground">
          {isWaking ? (
            <>
              Our server takes a quick nap when no one&apos;s around to keep things free and green.
              It&apos;s spinning back up now — this usually takes <strong>30–60 seconds</strong>.
              Hang tight, your food diary will be right with you.
            </>
          ) : (
            <>Getting things ready…</>
          )}
        </p>

        {/* Indeterminate progress bar */}
        <div className="mx-auto mb-6 h-1.5 w-full max-w-xs overflow-hidden rounded-full bg-secondary">
          <div className="h-full w-1/3 animate-[loadingbar_1.4s_ease-in-out_infinite] rounded-full bg-primary" />
        </div>

        <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin text-primary" />
          {isWaking ? <span>Waking up… {elapsed}s</span> : <span>Checking server…</span>}
        </div>

        {isWaking && (
          <div className="mt-8">
            <Button variant="outline" size="sm" onClick={retryNow}>
              Try again now
            </Button>
            <p className="mt-3 text-xs text-muted-foreground">
              Taking longer than a minute? It should connect any moment — thanks for your patience.
            </p>
          </div>
        )}
      </div>

      {/* Keyframes for the indeterminate bar (scoped, self-contained). */}
      <style>{`
        @keyframes loadingbar {
          0% { transform: translateX(-110%); }
          100% { transform: translateX(410%); }
        }
      `}</style>
    </div>
  );
}
