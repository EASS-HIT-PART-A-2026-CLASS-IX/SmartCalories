import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { LogOut, Save } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import { useAuthStore } from '@/stores/authStore';
import { usePrefsStore, type Theme, type Language, type Units } from '@/stores/prefsStore';
import { signInWithGoogle } from '@/lib/firebase';
import { firebaseConfigured } from '@/lib/env';
import { usersApi } from '@/lib/api/domain';
import { useLogout } from '@/hooks/useLogout';

const FILTERS = ['vegetarian', 'vegan', 'halal', 'kosher', 'gluten-free', 'dairy-free'];

export default function ProfileRoute() {
  const { t } = useTranslation();
  const auth = useAuthStore();
  const prefs = usePrefsStore();
  const qc = useQueryClient();

  const goals = useQuery({ queryKey: ['users', 'goals'], queryFn: usersApi.goals });
  const logout = useLogout();
  const [form, setForm] = useState({
    daily_kcal: '',
    protein_g: '',
    carb_g: '',
    fat_g: '',
  });

  useEffect(() => {
    if (goals.data) {
      setForm({
        daily_kcal: goals.data.daily_kcal?.toString() ?? '',
        protein_g: goals.data.protein_g?.toString() ?? '',
        carb_g: goals.data.carb_g?.toString() ?? '',
        fat_g: goals.data.fat_g?.toString() ?? '',
      });
    }
  }, [goals.data]);

  const saveGoals = useMutation({
    mutationFn: () =>
      usersApi.putGoals({
        daily_kcal: numberOr(form.daily_kcal),
        protein_g: numberOr(form.protein_g),
        carb_g: numberOr(form.carb_g),
        fat_g: numberOr(form.fat_g),
        dietary_filters: prefs.dietaryFilters,
      }),
    onSuccess: () => {
      toast.success('Saved');
      qc.invalidateQueries({ queryKey: ['users', 'goals'] });
      qc.invalidateQueries({ queryKey: ['insights'] });
    },
  });

  const toggleFilter = (filter: string) => {
    const next = prefs.dietaryFilters.includes(filter)
      ? prefs.dietaryFilters.filter((f) => f !== filter)
      : [...prefs.dietaryFilters, filter];
    prefs.setDietaryFilters(next);
  };

  return (
    <div className="mx-auto h-full max-w-3xl space-y-4 overflow-y-auto p-6">
      <Card>
        <CardHeader>
          <CardTitle>{t('nav.profile')}</CardTitle>
          <CardDescription>{t('empty.profile')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-medium">
                {auth.isAnonymous ? t('auth.guest') : auth.email ?? auth.displayName ?? '—'}
              </div>
              <div className="text-xs text-muted-foreground">{auth.isAnonymous ? 'Guest session' : 'Signed in'}</div>
            </div>
            {auth.uid ? (
              <div className="flex flex-col items-end gap-1">
                {auth.isAnonymous && firebaseConfigured() && (
                  <Button onClick={() => void signInWithGoogle()}>{t('actions.signIn')}</Button>
                )}
                <Button variant="ghost" size="sm" onClick={() => void logout()}>
                  <LogOut className="me-2 h-3 w-3" />
                  {t('actions.signOut')}
                </Button>
              </div>
            ) : null}
          </div>

          <Separator />

          <div className="grid gap-3 sm:grid-cols-3">
            <LabeledSelect
              label="Theme"
              value={prefs.theme}
              onChange={(v) => prefs.setTheme(v as Theme)}
              options={[
                ['light', 'Light'],
                ['dark', 'Dark'],
                ['system', 'System'],
              ]}
            />
            <LabeledSelect
              label="Language"
              value={prefs.language}
              onChange={(v) => prefs.setLanguage(v as Language)}
              options={[
                ['en', 'English'],
                ['he', 'עברית'],
              ]}
            />
            <LabeledSelect
              label="Units"
              value={prefs.units}
              onChange={(v) => prefs.setUnits(v as Units)}
              options={[
                ['metric', 'Metric'],
                ['imperial', 'Imperial'],
              ]}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Daily targets</CardTitle>
          <CardDescription>
            Ask the agent ("compute my TDEE — 75 kg, 178 cm, 30, male, moderate") to fill these in
            automatically, or edit directly.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {goals.isLoading ? (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i}>
                  <Skeleton className="mb-1 h-3 w-20" />
                  <Skeleton className="h-9 w-full" />
                </div>
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <NumField label="Daily kcal" value={form.daily_kcal} onChange={(v) => setForm({ ...form, daily_kcal: v })} />
              <NumField label="Protein (g)" value={form.protein_g} onChange={(v) => setForm({ ...form, protein_g: v })} />
              <NumField label="Carb (g)" value={form.carb_g} onChange={(v) => setForm({ ...form, carb_g: v })} />
              <NumField label="Fat (g)" value={form.fat_g} onChange={(v) => setForm({ ...form, fat_g: v })} />
            </div>
          )}

          <div>
            <div className="mb-1 text-sm text-muted-foreground">Dietary filters</div>
            <div className="flex flex-wrap gap-2">
              {FILTERS.map((f) => {
                const on = prefs.dietaryFilters.includes(f);
                return (
                  <button
                    key={f}
                    type="button"
                    onClick={() => toggleFilter(f)}
                    className={
                      'rounded-full border px-3 py-1 text-xs transition-colors ' +
                      (on
                        ? 'bg-primary text-primary-foreground border-primary'
                        : 'bg-background hover:bg-secondary')
                    }
                  >
                    {f}
                  </button>
                );
              })}
            </div>
          </div>

          <Button onClick={() => saveGoals.mutate()} disabled={saveGoals.isPending}>
            <Save className="me-2 h-3 w-3" /> Save goals
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

function NumField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <label className="text-sm">
      <span className="mb-1 block text-muted-foreground">{label}</span>
      <Input type="number" inputMode="decimal" value={value} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}

function LabeledSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: ReadonlyArray<readonly [string, string]>;
}) {
  return (
    <label className="text-sm">
      <span className="mb-1 block text-muted-foreground">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="block h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
      >
        {options.map(([v, l]) => (
          <option key={v} value={v}>
            {l}
          </option>
        ))}
      </select>
    </label>
  );
}

function numberOr(v: string): number | null {
  if (!v) return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}
