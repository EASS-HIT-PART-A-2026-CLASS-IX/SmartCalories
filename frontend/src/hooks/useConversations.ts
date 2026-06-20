import { useQuery } from '@tanstack/react-query';

import { listConversations, type Conversation } from '@/lib/api/chat';
import { useAuthStore } from '@/stores/authStore';

/**
 * Single source of truth for the user's chat conversation list. AuthProvider prefetches it
 * once on auth-ready, so this hook usually returns cached data with no network request.
 *
 * Mutations (new chat, send message → auto-titling) explicitly invalidate the
 * `['conversations']` query so the sidebar + history tab refresh.
 */
export function useConversations() {
  const authReady = useAuthStore((s) => s.ready);
  const uid = useAuthStore((s) => s.uid);
  return useQuery<Conversation[]>({
    queryKey: ['conversations'],
    queryFn: listConversations,
    enabled: authReady && !!uid,
    staleTime: 5 * 60 * 1000,
  });
}
