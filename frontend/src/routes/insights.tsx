import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { EmptyState } from '@/components/feedback/EmptyState';
import { ChartSkeleton } from '@/components/feedback/Skeletons';
import { Skeleton } from '@/components/ui/skeleton';
import { insightsApi, logsApi } from '@/lib/api/domain';

function avg(vals: number[]): number {
  const nonZero = vals.filter((v) => v > 0);
  if (!nonZero.length) return 0;
  return Math.round(nonZero.reduce((s, v) => s + v, 0) / nonZero.length);
}

function StatCard({
  label,
  value,
  unit,
  loading,
}: {
  label: string;
  value: number;
  unit: string;
  loading: boolean;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm text-muted-foreground">{label}</CardTitle>
      </CardHeader>
      <CardContent className="text-3xl font-semibold">
        {loading ? (
          <Skeleton className="h-8 w-20" />
        ) : (
          <>
            {value}
            <span className="ml-1 text-base font-normal text-muted-foreground">{unit}</span>
          </>
        )}
      </CardContent>
    </Card>
  );
}

export default function InsightsRoute() {
  const { t } = useTranslation();
  const range = useQuery({ queryKey: ['insights', 'range', 7], queryFn: () => insightsApi.range(7) });
  const streak = useQuery({ queryKey: ['insights', 'streak'], queryFn: insightsApi.streak });
  const logs = useQuery({ queryKey: ['logs', 'range', 7], queryFn: () => logsApi.range(7) });

  const initialLoading = range.isLoading && streak.isLoading && logs.isLoading;
  if (initialLoading) {
    return (
      <div className="mx-auto h-full max-w-4xl space-y-4 overflow-y-auto p-6">
        <ChartSkeleton />
      </div>
    );
  }

  const days = range.data ?? [];
  const data = days.map((d) => ({
    date: d.date.slice(5),
    kcal: d.calories,
    target: d.target_kcal ?? 0,
  }));
  const hasData = data.some((d) => d.kcal > 0);

  const avgKcal = avg(days.map((d) => d.calories));
  const avgProtein = avg(days.map((d) => d.protein_g));
  const avgCarb = avg(days.map((d) => d.carb_g));
  const avgFat = avg(days.map((d) => d.fat_g));
  const goalKcal = days.find((d) => d.target_kcal)?.target_kcal ?? 0;

  return (
    <div className="mx-auto h-full max-w-4xl space-y-4 overflow-y-auto p-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Streak"
          value={streak.data?.days ?? 0}
          unit="days"
          loading={streak.isLoading}
        />
        <StatCard
          label="Water (7d)"
          value={logs.data ? Math.round((logs.data.water_ml_total ?? 0) / 1000) : 0}
          unit="L"
          loading={logs.isLoading}
        />
        <StatCard label="Avg kcal (7d)" value={avgKcal} unit="kcal" loading={range.isLoading} />
        <StatCard
          label="Avg protein (7d)"
          value={avgProtein}
          unit="g"
          loading={range.isLoading}
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard label="Avg carbs (7d)" value={avgCarb} unit="g" loading={range.isLoading} />
        <StatCard label="Avg fat (7d)" value={avgFat} unit="g" loading={range.isLoading} />
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted-foreground">Goal (daily)</CardTitle>
          </CardHeader>
          <CardContent className="text-3xl font-semibold">
            {range.isLoading ? (
              <Skeleton className="h-8 w-20" />
            ) : (
              <>
                {goalKcal || '—'}
                {goalKcal ? (
                  <span className="ml-1 text-base font-normal text-muted-foreground">kcal</span>
                ) : null}
              </>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Calories — last 7 days</CardTitle>
        </CardHeader>
        <CardContent className="h-72">
          {range.isLoading ? (
            <div className="flex h-full items-end gap-2">
              {Array.from({ length: 7 }).map((_, i) => (
                <Skeleton key={i} className="flex-1" style={{ height: `${30 + ((i * 17) % 60)}%` }} />
              ))}
            </div>
          ) : hasData ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="date" stroke="hsl(var(--muted-foreground))" fontSize={12} />
                <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} />
                <Tooltip
                  contentStyle={{
                    background: 'hsl(var(--card))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '0.5rem',
                  }}
                />
                {goalKcal > 0 && (
                  <ReferenceLine
                    y={goalKcal}
                    stroke="hsl(var(--primary))"
                    strokeDasharray="6 3"
                    strokeOpacity={0.6}
                    label={{
                      value: `Goal ${goalKcal}`,
                      position: 'insideTopRight',
                      fill: 'hsl(var(--primary))',
                      fontSize: 11,
                    }}
                  />
                )}
                <Bar dataKey="kcal" fill="hsl(var(--primary))" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState description={t('empty.insights')} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
