import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ChevronLeft, ChevronRight, Droplet, Plus, Trash2 } from 'lucide-react';
import dayjs from 'dayjs';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { EmptyState } from '@/components/feedback/EmptyState';
import { ListRowsSkeleton, StatGridSkeleton } from '@/components/feedback/Skeletons';
import { diaryApi, insightsApi, logsApi, usersApi } from '@/lib/api/domain';

export default function DiaryRoute() {
  const qc = useQueryClient();
  const [name, setName] = useState('');
  const [kcal, setKcal] = useState('');
  const [meal, setMeal] = useState('snack');
  const [offset, setOffset] = useState(0); // 0 = today, -1 = yesterday, …

  const selectedDay = dayjs().add(offset, 'day');
  const isToday = offset === 0;
  const dayLabel = isToday ? 'Today' : offset === -1 ? 'Yesterday' : selectedDay.format('MMM D');

  const from = selectedDay.startOf('day').toISOString();
  const to = selectedDay.endOf('day').toISOString();

  const entries = useQuery({
    queryKey: ['diary', 'range', from],
    queryFn: () => diaryApi.range(from, to),
  });
  const macros = useQuery({ queryKey: ['insights', 'today'], queryFn: insightsApi.today, enabled: isToday });
  const goals = useQuery({ queryKey: ['users', 'goals'], queryFn: usersApi.goals });
  const logsToday = useQuery({ queryKey: ['logs', 'today'], queryFn: () => logsApi.range(1), enabled: isToday });

  const create = useMutation({
    mutationFn: (input: { name: string; calories: number; meal: string }) => diaryApi.create(input),
    onSuccess: (entry) => {
      setName('');
      setKcal('');
      void qc.invalidateQueries({ queryKey: ['diary', 'range'] });
      void qc.invalidateQueries({ queryKey: ['insights', 'today'] });
      toast.success(`Logged ${entry.name} (${entry.calories} kcal)`);
    },
    onError: () => toast.error('Failed to log entry'),
  });
  const remove = useMutation({
    mutationFn: (id: number) => diaryApi.delete(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['diary', 'range'] });
      void qc.invalidateQueries({ queryKey: ['insights', 'today'] });
    },
    onError: () => toast.error('Failed to delete entry'),
  });

  /** Delete with a 6-second Undo toast: re-creates the entry server-side if the user undoes. */
  const removeWithUndo = (entry: { id: number; name: string; calories: number; meal: string }) => {
    remove.mutate(entry.id);
    toast(`Deleted "${entry.name}"`, {
      duration: 6000,
      action: {
        label: 'Undo',
        onClick: () =>
          create.mutate({ name: entry.name, calories: entry.calories, meal: entry.meal }),
      },
    });
  };
  const water = useMutation({
    mutationFn: () => logsApi.water(250),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['logs', 'today'] });
      toast.success('+250 ml water logged');
    },
  });

  // Compute macros from entries for past days; use server-side macros for today
  const dayEntries = entries.data ?? [];
  const computedCals = dayEntries.reduce((s, e) => s + e.calories, 0);
  const computedProtein = dayEntries.reduce((s, e) => s + (e.protein_g ?? 0), 0);
  const computedCarb = dayEntries.reduce((s, e) => s + (e.carb_g ?? 0), 0);
  const computedFat = dayEntries.reduce((s, e) => s + (e.fat_g ?? 0), 0);

  const m = isToday ? macros.data : null;
  const displayCals = m?.calories ?? computedCals;
  const displayProtein = m?.protein_g ?? computedProtein;
  const displayCarb = m?.carb_g ?? computedCarb;
  const displayFat = m?.fat_g ?? computedFat;
  const g = goals.data;

  return (
    <div className="mx-auto h-full max-w-3xl space-y-4 overflow-y-auto p-6">
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle>{dayLabel}</CardTitle>
            <div className="flex items-center gap-1">
              <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => setOffset((o) => o - 1)}>
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="min-w-[80px] text-center text-xs text-muted-foreground">
                {isToday ? 'Today' : selectedDay.format('MMM D, YYYY')}
              </span>
              <Button
                size="icon"
                variant="ghost"
                className="h-7 w-7"
                onClick={() => setOffset((o) => o + 1)}
                disabled={isToday}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {(isToday ? macros.isLoading : entries.isLoading) ? (
            <StatGridSkeleton />
          ) : (
            <div className="grid grid-cols-4 gap-3">
              <Stat label="kcal" value={displayCals} target={m?.target_kcal ?? g?.daily_kcal ?? null} />
              <Stat label="P (g)" value={displayProtein} target={m?.target_protein_g ?? g?.protein_g ?? null} />
              <Stat label="C (g)" value={displayCarb} target={m?.target_carb_g ?? g?.carb_g ?? null} />
              <Stat label="F (g)" value={displayFat} target={m?.target_fat_g ?? g?.fat_g ?? null} />
            </div>
          )}
          {isToday && (
            <div className="mt-3 flex items-center gap-3">
              <Button
                size="sm"
                variant="outline"
                onClick={() => water.mutate()}
                disabled={water.isPending}
              >
                <Droplet className="me-1 h-3 w-3" />+250ml
              </Button>
              <span className="text-xs tabular-nums text-muted-foreground">
                {logsToday.isLoading
                  ? '…'
                  : `Water today: ${((logsToday.data?.water_ml_total ?? 0) / 1000).toFixed(2)} L`}
              </span>
            </div>
          )}
        </CardContent>
      </Card>

      {isToday && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle>Quick log</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap items-end gap-2">
              <Input
                className="flex-1 min-w-[180px]"
                placeholder="Food name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && name && kcal)
                    create.mutate({ name, calories: Number(kcal), meal });
                }}
              />
              <Input
                className="w-24"
                placeholder="kcal"
                type="number"
                value={kcal}
                onChange={(e) => setKcal(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && name && kcal)
                    create.mutate({ name, calories: Number(kcal), meal });
                }}
              />
              <select
                value={meal}
                onChange={(e) => setMeal(e.target.value)}
                className="h-9 rounded-md border border-input bg-background px-2 text-sm"
              >
                <option value="breakfast">Breakfast</option>
                <option value="lunch">Lunch</option>
                <option value="dinner">Dinner</option>
                <option value="snack">Snack</option>
              </select>
              <Button
                onClick={() => create.mutate({ name, calories: Number(kcal), meal })}
                disabled={!name || !kcal || create.isPending}
              >
                <Plus className="me-1 h-3 w-3" /> Add
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {entries.isLoading ? (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle>Entries</CardTitle>
          </CardHeader>
          <CardContent>
            <ListRowsSkeleton rows={4} />
          </CardContent>
        </Card>
      ) : dayEntries.length === 0 ? (
        <EmptyState description={isToday ? 'No entries yet today. Use the Chat tab or tap + to log.' : `No entries for ${selectedDay.format('MMM D')}`} />
      ) : (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle>Entries</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {groupByMeal(dayEntries).map((group) => (
              <div key={group.meal} className="space-y-1">
                <div className="flex items-baseline justify-between border-b pb-1 text-xs uppercase tracking-wider text-muted-foreground">
                  <span className="font-medium">{group.meal}</span>
                  <span className="tabular-nums">
                    {group.items.reduce((s, i) => s + i.calories, 0)} kcal
                  </span>
                </div>
                {group.items.map((e) => (
                  <div
                    key={e.id}
                    className="flex items-center gap-3 rounded-md p-2 hover:bg-secondary"
                  >
                    <span className="flex-1 truncate text-sm">{e.name}</span>
                    <span className="text-xs tabular-nums">{e.calories} kcal</span>
                    <span className="text-[10px] text-muted-foreground tabular-nums">
                      {dayjs(e.eaten_at).format('HH:mm')}
                    </span>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() =>
                        removeWithUndo({
                          id: e.id,
                          name: e.name,
                          calories: e.calories,
                          meal: e.meal,
                        })
                      }
                      className="h-7 w-7 text-muted-foreground opacity-60 hover:opacity-100 hover:text-destructive"
                      aria-label={`Delete ${e.name}`}
                      title={`Delete ${e.name}`}
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </div>
                ))}
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

const MEAL_ORDER = ['breakfast', 'lunch', 'dinner', 'snack'] as const;

function groupByMeal(entries: { id: number; name: string; calories: number; meal: string; eaten_at: string }[]) {
  const map = new Map<string, typeof entries>();
  for (const e of entries) {
    const key = (e.meal || 'snack').toLowerCase();
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(e);
  }
  // Sort each group by eaten_at; sort groups by canonical meal order, with unknowns last.
  for (const list of map.values()) list.sort((a, b) => a.eaten_at.localeCompare(b.eaten_at));
  return Array.from(map.entries())
    .sort(([a], [b]) => {
      const ai = MEAL_ORDER.indexOf(a as (typeof MEAL_ORDER)[number]);
      const bi = MEAL_ORDER.indexOf(b as (typeof MEAL_ORDER)[number]);
      return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
    })
    .map(([meal, items]) => ({ meal: meal[0].toUpperCase() + meal.slice(1), items }));
}

function Stat({ label, value, target }: { label: string; value: number; target: number | null }) {
  const pct = target ? Math.min(100, Math.round((value / target) * 100)) : null;
  return (
    <div className="rounded-md border bg-card p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-xl font-semibold tabular-nums">{Math.round(value)}</div>
      {target && (
        <div className="mt-1 text-[10px] text-muted-foreground">
          / {Math.round(target)} ({pct}%)
        </div>
      )}
    </div>
  );
}
