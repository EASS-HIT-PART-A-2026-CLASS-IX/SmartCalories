import { User as UserIcon } from 'lucide-react';
import { cn } from '@/lib/utils';

interface UserAvatarProps {
  photoUrl?: string | null;
  displayName?: string | null;
  size?: number;
  className?: string;
}

/**
 * Shows the signed-in user's photo when available, falling back to a generic person icon.
 * Single source of truth so sidebar + chat bubbles render identically.
 */
export function UserAvatar({ photoUrl, displayName, size = 28, className }: UserAvatarProps) {
  const initials = (displayName ?? '')
    .split(/\s+/)
    .map((p) => p[0])
    .filter(Boolean)
    .slice(0, 2)
    .join('')
    .toUpperCase();

  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-secondary text-secondary-foreground',
        className,
      )}
      style={{ width: size, height: size }}
      aria-label={displayName ?? 'User'}
    >
      {photoUrl ? (
        <img
          src={photoUrl}
          alt={displayName ?? 'User'}
          className="h-full w-full object-cover"
          referrerPolicy="no-referrer"
        />
      ) : initials ? (
        <span className="text-[10px] font-medium">{initials}</span>
      ) : (
        <UserIcon className="h-1/2 w-1/2" />
      )}
    </span>
  );
}
