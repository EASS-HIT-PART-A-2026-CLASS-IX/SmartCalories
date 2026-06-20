import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type Theme = 'light' | 'dark' | 'system';
export type Language = 'en' | 'he';
export type Units = 'metric' | 'imperial';

interface PrefsState {
  theme: Theme;
  language: Language;
  units: Units;
  dietaryFilters: string[];
  setTheme: (t: Theme) => void;
  setLanguage: (l: Language) => void;
  setUnits: (u: Units) => void;
  setDietaryFilters: (f: string[]) => void;
}

export const usePrefsStore = create<PrefsState>()(
  persist(
    (set) => ({
      theme: 'system',
      language: 'en',
      units: 'metric',
      dietaryFilters: [],
      setTheme: (theme) => {
        set({ theme });
        applyTheme(theme);
      },
      setLanguage: (language) => {
        set({ language });
        applyLanguage(language);
      },
      setUnits: (units) => set({ units }),
      setDietaryFilters: (dietaryFilters) => set({ dietaryFilters }),
    }),
    { name: 'sc.prefs.v1' },
  ),
);

export function applyTheme(theme: Theme): void {
  const dark =
    theme === 'dark' ||
    (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.classList.toggle('dark', dark);
}

export function applyLanguage(lang: Language): void {
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === 'he' ? 'rtl' : 'ltr';
}
