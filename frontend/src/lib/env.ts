export const env = {
  apiBase: import.meta.env.VITE_API_BASE ?? '',
  firebase: {
    apiKey: import.meta.env.VITE_FB_API_KEY ?? '',
    authDomain: import.meta.env.VITE_FB_AUTH_DOMAIN ?? '',
    projectId: import.meta.env.VITE_FB_PROJECT_ID ?? '',
    appId: import.meta.env.VITE_FB_APP_ID ?? '',
  },
  allowGuest: (import.meta.env.VITE_ALLOW_GUEST ?? '1') !== '0',
};

export function firebaseConfigured(): boolean {
  return Boolean(env.firebase.apiKey && env.firebase.projectId && env.firebase.appId);
}
