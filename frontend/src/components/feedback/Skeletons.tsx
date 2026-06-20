import { Skeleton } from '@/components/ui/skeleton';
import { Card, CardContent, CardHeader } from '@/components/ui/card';

/** A row of stat blocks (kcal/protein/carb/fat). Used in Diary. */
export function StatGridSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className={`grid gap-3 sm:grid-cols-${count}`}>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="rounded-md border bg-card p-3">
          <Skeleton className="mb-2 h-3 w-12" />
          <Skeleton className="h-7 w-16" />
          <Skeleton className="mt-2 h-2 w-20" />
        </div>
      ))}
    </div>
  );
}

/** Generic list-of-rows placeholder (diary entries, history). */
export function ListRowsSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="space-y-1">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-3 p-2">
          <Skeleton className="h-3 w-16" />
          <Skeleton className="h-4 flex-1" />
          <Skeleton className="h-3 w-12" />
        </div>
      ))}
    </div>
  );
}

/** Bar-chart placeholder with stat-card row above. Used in Insights. */
export function ChartSkeleton() {
  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="rounded-md border bg-card p-4">
            <Skeleton className="mb-2 h-3 w-20" />
            <Skeleton className="h-8 w-16" />
          </div>
        ))}
      </div>
      <Card>
        <CardHeader>
          <Skeleton className="h-4 w-48" />
        </CardHeader>
        <CardContent>
          <div className="flex h-64 items-end gap-2">
            {Array.from({ length: 7 }).map((_, i) => (
              <Skeleton key={i} className="flex-1" style={{ height: `${30 + ((i * 17) % 60)}%` }} />
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
