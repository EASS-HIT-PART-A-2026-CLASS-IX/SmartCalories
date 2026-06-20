/**
 * Firebase Auth. Three sign-in paths only: Google OAuth, anonymous (guest), and demo
 * (handled out-of-band by the backend's /auth/demo endpoint).
 */
import { initializeApp, type FirebaseApp } from 'firebase/app';
import {
  GoogleAuthProvider,
  type Auth,
  type User,
  getAuth,
  linkWithPopup,
  onIdTokenChanged,
  signInAnonymously,
  signInWithPopup,
  signOut as fbSignOut,
} from 'firebase/auth';

import { env, firebaseConfigured } from './env';

let app: FirebaseApp | null = null;
let auth: Auth | null = null;

function ensureApp(): { app: FirebaseApp; auth: Auth } | null {
  if (!firebaseConfigured()) return null;
  if (app && auth) return { app, auth };
  app = initializeApp({
    apiKey: env.firebase.apiKey,
    authDomain: env.firebase.authDomain,
    projectId: env.firebase.projectId,
    appId: env.firebase.appId,
  });
  auth = getAuth(app);
  return { app, auth };
}

export function getFirebaseAuth(): Auth | null {
  return ensureApp()?.auth ?? null;
}

export async function signInGuest(): Promise<void> {
  const a = getFirebaseAuth();
  if (!a) return;
  await signInAnonymously(a);
}

/** Sign out of Firebase (if active) so the demo session can replace it cleanly. */
export async function clearFirebaseSession(): Promise<void> {
  const a = getFirebaseAuth();
  if (a?.currentUser) await fbSignOut(a);
}

export async function signInWithGoogle(): Promise<void> {
  const a = getFirebaseAuth();
  if (!a) return;
  const provider = new GoogleAuthProvider();
  if (a.currentUser?.isAnonymous) {
    await linkWithPopup(a.currentUser, provider);
  } else {
    await signInWithPopup(a, provider);
  }
}

export async function signOut(): Promise<void> {
  const a = getFirebaseAuth();
  if (a) await fbSignOut(a);
}

export function watchIdToken(cb: (user: User | null, token: string | null) => void): () => void {
  const a = getFirebaseAuth();
  if (!a) {
    cb(null, null);
    return () => {};
  }
  return onIdTokenChanged(a, async (user) => {
    if (!user) {
      cb(null, null);
      return;
    }
    const token = await user.getIdToken();
    cb(user, token);
  });
}

export async function refreshIdToken(): Promise<string | null> {
  const a = getFirebaseAuth();
  if (!a?.currentUser) return null;
  return a.currentUser.getIdToken(true);
}
