import { useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';

import { signOut } from '@/lib/firebase';
import { useAuthStore } from '@/stores/authStore';

/**
 * Universal logout. Works for every kind of session we support:
 * - Firebase real users → Firebase signOut
 * - Firebase anonymous (guest) → Firebase signOut
 * - Demo (no Firebase) → just reset the store
 *
 * Also wipes the persisted demo state from localStorage and clears the React Query cache so
 * the next user can't see the previous user's data on the bridge between logout and login.
 */
export function useLogout() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const reset = useAuthStore((s) => s.reset);

  return async () => {
    try {
      await signOut();
    } catch {
      /* not signed in to Firebase — fine */
    }
    reset();
    try {
      localStorage.removeItem('sc.auth.v1');
    } catch {
      /* ignore */
    }
    queryClient.clear();
    navigate('/login', { replace: true });
  };
}
