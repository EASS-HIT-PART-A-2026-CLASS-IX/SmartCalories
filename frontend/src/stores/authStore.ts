import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface AuthState {
  uid: string | null;
  email: string | null;
  displayName: string | null;
  photoUrl: string | null;
  isAnonymous: boolean;
  idToken: string | null;
  loading: boolean;
  ready: boolean;
  setUser: (u: {
    uid: string | null;
    email?: string | null;
    displayName?: string | null;
    photoUrl?: string | null;
    isAnonymous?: boolean;
    idToken?: string | null;
  }) => void;
  setReady: (v: boolean) => void;
  reset: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      uid: null,
      email: null,
      displayName: null,
      photoUrl: null,
      isAnonymous: false,
      idToken: null,
      loading: true,
      ready: false,
      setUser: (u) =>
        set({
          uid: u.uid,
          email: u.email ?? null,
          displayName: u.displayName ?? null,
          photoUrl: u.photoUrl ?? null,
          isAnonymous: u.isAnonymous ?? false,
          idToken: u.idToken ?? null,
          loading: false,
        }),
      setReady: (v) => set({ ready: v }),
      reset: () =>
        set({
          uid: null,
          email: null,
          displayName: null,
          photoUrl: null,
          isAnonymous: false,
          idToken: null,
          loading: false,
        }),
    }),
    {
      name: 'sc.auth.v1',
      // Only persist demo sessions: Firebase users are persisted by Firebase IndexedDB and
      // re-hydrated via onIdTokenChanged on boot. Returning `undefined` makes Zustand skip
      // the write entirely (no stale write that could later overwrite live Firebase state).
      partialize: (state) =>
        state.uid?.startsWith('demo-')
          ? ({
              uid: state.uid,
              email: state.email,
              displayName: state.displayName,
              photoUrl: state.photoUrl,
              isAnonymous: state.isAnonymous,
              idToken: state.idToken,
            } as Partial<AuthState>)
          : (undefined as unknown as Partial<AuthState>),
      // The default merge shallow-overwrites the in-memory store with the persisted slice on
      // hydration — racing AuthProvider's setUser. Only merge when the persisted slice is a
      // demo session; otherwise keep whatever AuthProvider has set so far.
      merge: (persistedState, currentState) => {
        const p = persistedState as Partial<AuthState> | undefined | null;
        if (p?.uid?.startsWith('demo-')) {
          return { ...currentState, ...p, ready: false };
        }
        return currentState;
      },
    },
  ),
);
