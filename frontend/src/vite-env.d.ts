/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
  readonly VITE_FB_API_KEY?: string;
  readonly VITE_FB_AUTH_DOMAIN?: string;
  readonly VITE_FB_PROJECT_ID?: string;
  readonly VITE_FB_APP_ID?: string;
  readonly VITE_ALLOW_GUEST?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
