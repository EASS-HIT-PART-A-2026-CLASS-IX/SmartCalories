import { useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';

import { env, firebaseConfigured } from '@/lib/env';
import { watchIdToken } from '@/lib/firebase';
import { useAuthStore } from '@/stores/authStore';
import { listConversations, listMessages } from '@/lib/api/chat';

const DEMO_UID_PREFIX = 'demo-';

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const setUser = useAuthStore((s) => s.setUser);
  const setReady = useAuthStore((s) => s.setReady);
  const reset = useAuthStore((s) => s.reset);
  const queryClient = useQueryClient();
  const lastUid = useRef<string | null>(null);
  const ranOnce = useRef(false);

  // Whenever a real (non-null) uid lands in the store, eagerly warm the conversations cache,
  // then fan out and warm each session's messages cache too. After this runs, switching
  // between conversations is instant — no spinner, no fetch on click.
  // Capped at 30 most-recent sessions to keep the boot cost bounded.
  const uid = useAuthStore((s) => s.uid);
  useEffect(() => {
    if (!uid) return;
    let cancelled = false;
    void (async () => {
      const STALE = 5 * 60 * 1000;
      try {
        const conversations = await queryClient.fetchQuery({
          queryKey: ['conversations'],
          queryFn: listConversations,
          staleTime: STALE,
        });
        if (cancelled || !conversations.length) return;
        const recent = conversations.slice(0, 30);
        await Promise.all(
          recent.map((c) =>
            queryClient
              .prefetchQuery({
                queryKey: ['conversation', c.id, 'messages'],
                queryFn: () => listMessages(c.id),
                staleTime: STALE,
              })
              .catch(() => {}),
          ),
        );
      } catch {
        /* prefetch is best-effort; per-tab queries will retry on click */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [uid, queryClient]);

  useEffect(() => {
    if (ranOnce.current) return;
    ranOnce.current = true;

    if (!firebaseConfigured()) {
      console.info('[auth] firebase not configured — entering demo mode');
      setUser({
        uid: 'demo-uid',
        email: null,
        displayName: 'Demo',
        isAnonymous: true,
        idToken: 'demo-token',
      });
      setReady(true);
      return;
    }

    console.info('[auth] firebase configured, project=', env.firebase.projectId);

    window.setTimeout(() => {
      if (!useAuthStore.getState().ready) {
        console.warn('[auth] failsafe: no Firebase state in 4s — routing to /login');
        reset();
        setReady(true);
      }
    }, 4000);

    watchIdToken((user, token) => {
      const currentUid = useAuthStore.getState().uid;
      console.info('[auth] onIdTokenChanged user=', user?.uid ?? 'null', 'storeUid=', currentUid);

      // Demo session is the source of truth — ignore Firebase entirely (token refresh,
      // signOut, etc.) once a demo uid is in the store. Otherwise refresh + sign-out events
      // would race-overwrite the demo state.
      if (currentUid?.startsWith(DEMO_UID_PREFIX)) {
        setReady(true);
        return;
      }

      if (user) {
        if (lastUid.current && lastUid.current !== user.uid) {
          console.info('[auth] uid transition: clearing query cache');
          queryClient.clear();
        }
        lastUid.current = user.uid;
        setUser({
          uid: user.uid,
          email: user.email,
          displayName: user.displayName,
          photoUrl: user.photoURL,
          isAnonymous: user.isAnonymous,
          idToken: token,
        });
        setReady(true);
        return;
      }

      // No signed-in user and no demo session → show the login screen (Demo / Google).
      // There is no anonymous "guest" auto-sign-in anymore.
      reset();
      setReady(true);
    });
  }, [setUser, setReady, reset, queryClient]);

  return <>{children}</>;
}
