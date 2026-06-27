import { api } from './client';

export interface DiaryEntry {
  id: number;
  name: string;
  calories: number;
  protein_g: number;
  carb_g: number;
  fat_g: number;
  serving_qty: number;
  serving_unit: string;
  meal: string;
  eaten_at: string;
  source: string;
  image_path: string | null;
  barcode: string | null;
  notes: string | null;
}

export interface MacrosSnapshot {
  date: string;
  calories: number;
  protein_g: number;
  carb_g: number;
  fat_g: number;
  target_kcal: number | null;
  target_protein_g: number | null;
  target_carb_g: number | null;
  target_fat_g: number | null;
}

export interface UserGoals {
  daily_kcal: number | null;
  protein_g: number | null;
  carb_g: number | null;
  fat_g: number | null;
  tdee: number | null;
  activity_level: string | null;
  dietary_filters: string[];
  weight_kg: number | null;
  height_cm: number | null;
  sex: string | null;
}

export const diaryApi = {
  range: (from: string, to: string) =>
    api<DiaryEntry[]>('/diary', { query: { from, to } }),
  create: (body: { name: string; calories: number; meal: string }) =>
    api<DiaryEntry>('/diary', { method: 'POST', json: body }),
  delete: (id: number) => api<void>(`/diary/${id}`, { method: 'DELETE' }),
};

export const insightsApi = {
  today: () => api<MacrosSnapshot>('/insights/macros/today'),
};

export const usersApi = {
  goals: () => api<UserGoals>('/users/me/goals'),
};

export const logsApi = {
  water: (ml: number) => api('/logs/water', { method: 'POST', json: { ml } }),
  range: (days = 7) =>
    api<{ water_ml_total: number }>('/logs/range', { query: { days } }),
};

// --- Auth helpers (demo + playground) ---

export interface DemoSession {
  uid: string;
  token: string;
  email: string;
  display_name: string;
  is_anonymous: boolean;
  seeded: Record<string, number>;
}

export const startDemoSession = () => api<DemoSession>('/auth/demo', { method: 'POST' });
