import * as React from 'react';
import { Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';

interface EmptyStateProps {
  title?: string;
  description?: string;
  icon?: React.ReactNode;
  className?: string;
  children?: React.ReactNode;
}

export function EmptyState({ title, description, icon, className, children }: EmptyStateProps) {
  return (
    <div
      className={cn(
        'mx-auto flex max-w-md flex-col items-center justify-center gap-3 px-6 py-16 text-center text-muted-foreground',
        className,
      )}
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-accent text-accent-foreground">
        {icon ?? <Sparkles className="h-6 w-6" />}
      </div>
      {title && <h2 className="text-lg font-semibold text-foreground">{title}</h2>}
      {description && <p className="text-sm">{description}</p>}
      {children}
    </div>
  );
}
