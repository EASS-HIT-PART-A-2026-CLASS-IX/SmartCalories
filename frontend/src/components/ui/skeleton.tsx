import * as React from 'react';
import { cn } from '@/lib/utils';

/**
 * Animated placeholder block. Shows a subtle pulsing rounded rectangle while data is loading.
 * Use to fill the rough shape of the eventual content so the layout doesn't jump.
 */
export function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('animate-pulse rounded-md bg-muted/70 dark:bg-muted/40', className)}
      {...props}
    />
  );
}
