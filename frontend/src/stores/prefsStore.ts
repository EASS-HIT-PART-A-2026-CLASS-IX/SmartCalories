import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type Theme = 'light' | 'dark' | 'system';
export type Units = 'metric' | 'imperial';

interface PrefsState {
  theme: Theme;
  units: Units;
  dietaryFilters: string[];
  setTheme: (t: Theme) => void;
  setUnits: (u: Units) => void;
  setDietaryFilters: (f: string[]) => void;
}

export const usePrefsStore = create<PrefsState>()(
  persist(
    (set) => ({
      theme: 'system',
      units: 'metric',
      dietaryFilters: [],
      setTheme: (theme) => {
        set({ theme });
        applyTheme(theme);
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
