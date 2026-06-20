import { useEffect } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  ChevronLeft,
  ChevronRight,
  Compass,
  Github,
  History as HistoryIcon,
  LayoutDashboard,
  Linkedin,
  LogOut,
  MessageCircle,
  PanelLeftClose,
  PanelLeftOpen,
  Sparkles,
  User as UserIcon,
} from 'lucide-react';

import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { Badge } from '@/components/ui/badge';
import { useAuthStore } from '@/stores/authStore';
import { useUiStore } from '@/stores/uiStore';
import { UserAvatar } from '@/components/UserAvatar';
import { useLogout } from '@/hooks/useLogout';

type NavItem = { to: string; key: string; icon: React.ComponentType<{ className?: string }> };

const NAV: NavItem[] = [
  { to: '/', key: 'chat', icon: MessageCircle },
  { to: '/diary', key: 'diary', icon: LayoutDashboard },
  { to: '/insights', key: 'insights', icon: Compass },
  { to: '/history', key: 'history', icon: HistoryIcon },
  { to: '/profile', key: 'profile', icon: UserIcon },
];

export function AppShell() {
  const { t } = useTranslation();
  const location = useLocation();
  const ready = useAuthStore((s) => s.ready);
  const uid = useAuthStore((s) => s.uid);
  const photoUrl = useAuthStore((s) => s.photoUrl);
  const displayName = useAuthStore((s) => s.displayName);
  const email = useAuthStore((s) => s.email);
  const isAnonymous = useAuthStore((s) => s.isAnonymous);
  const navigate = useNavigate();
  const navCollapsed = useUiStore((s) => s.navCollapsed);
  const toggleNav = useUiStore((s) => s.toggleNav);
  const logout = useLogout();

  useEffect(() => {
    if (ready && !uid && location.pathname !== '/login') {
      navigate('/login', { replace: true });
    }
  }, [ready, uid, location.pathname, navigate]);

  if (!ready) {
    return (
      <div className="flex h-dvh items-center justify-center text-base text-muted-foreground">
        {t('loading')}
      </div>
    );
  }
  // No <Navigate> JSX — the useEffect above handles the redirect. Rendering Navigate alongside
  // the useEffect was causing a render-time navigation loop with React 18 StrictMode.
  if (!uid) {
    return (
      <div className="flex h-dvh items-center justify-center text-base text-muted-foreground">
        {t('loading')}
      </div>
    );
  }

  return (
    <div className="flex h-dvh w-full overflow-hidden bg-background text-foreground">
      <aside
        className={cn(
          'hidden shrink-0 flex-col border-e bg-card transition-[width] duration-200 md:flex',
          navCollapsed ? 'w-16' : 'w-64',
        )}
      >
        <div
          className={cn(
            'flex items-center gap-2 px-3 py-3',
            navCollapsed && 'flex-col gap-2 px-2',
          )}
        >
          <Link
            to="/"
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground shadow-sm"
            title={t('app.name')}
          >
            <Sparkles className="h-4 w-4" />
          </Link>
          {!navCollapsed && (
            <Link to="/" className="truncate text-base font-semibold tracking-tight">
              {t('app.name')}
            </Link>
          )}
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleNav}
            className={cn('h-8 w-8 shrink-0', !navCollapsed && 'ms-auto')}
            title={navCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {navCollapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
          </Button>
        </div>
        <Separator />
        <nav className="flex-1 space-y-1 overflow-y-auto p-2">
          {NAV.map(({ to, key, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              title={navCollapsed ? t(`nav.${key}`) : undefined}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors',
                  navCollapsed && 'justify-center px-2',
                  isActive
                    ? 'bg-accent text-accent-foreground font-medium'
                    : 'text-muted-foreground hover:bg-secondary hover:text-foreground',
                )
              }
            >
              <Icon className="h-5 w-5" />
              {!navCollapsed && <span>{t(`nav.${key}`)}</span>}
            </NavLink>
          ))}
        </nav>
        <Separator />
        <div className={cn('flex flex-col gap-2 p-3 text-xs', navCollapsed && 'items-center')}>
          {!navCollapsed ? (
            <div className="flex items-center gap-2">
              <UserAvatar photoUrl={photoUrl} displayName={displayName} size={32} />
              <div className="min-w-0 flex-1 leading-tight">
                <div className="truncate text-sm font-medium text-foreground">
                  {displayName ?? email ?? t('auth.guest')}
                </div>
                {isAnonymous && <Badge variant="secondary">guest</Badge>}
                {!isAnonymous && email && (
                  <div className="truncate text-[11px] text-muted-foreground">{email}</div>
                )}
              </div>
            </div>
          ) : (
            <UserAvatar photoUrl={photoUrl} displayName={displayName} size={32} />
          )}
          {isAnonymous && !navCollapsed && (
            <Button asChild variant="outline" size="sm" className="w-full">
              <Link to="/login">{t('actions.signIn')}</Link>
            </Button>
          )}
          {!navCollapsed && (
            <>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => void logout()}
                className="justify-start text-muted-foreground"
              >
                <LogOut className="me-2 h-3.5 w-3.5" />
                {t('actions.signOut')}
              </Button>
              <div className="flex items-center justify-end gap-2 pt-1 text-muted-foreground">
                <a
                  href="https://github.com/RoeiLevy"
                  target="_blank"
                  rel="noreferrer"
                  className="hover:text-foreground"
                  title="GitHub"
                >
                  <Github className="h-4 w-4" />
                </a>
                <a
                  href="https://www.linkedin.com/in/roei-levy99/"
                  target="_blank"
                  rel="noreferrer"
                  className="hover:text-foreground"
                  title="LinkedIn"
                >
                  <Linkedin className="h-4 w-4" />
                </a>
              </div>
            </>
          )}
        </div>
      </aside>

      <main className="relative flex flex-1 flex-col">
        <header className="flex h-14 items-center gap-2 border-b px-4 md:hidden">
          <Button variant="ghost" size="icon" onClick={toggleNav}>
            {navCollapsed ? <ChevronRight className="h-5 w-5" /> : <ChevronLeft className="h-5 w-5" />}
          </Button>
          <Sparkles className="h-5 w-5 text-primary" />
          <span className="font-semibold">{t('app.name')}</span>
          <div className="ms-auto flex items-center gap-1">
            {isAnonymous && (
              <Button variant="outline" size="sm" asChild>
                <Link to="/login">{t('actions.signIn')}</Link>
              </Button>
            )}
            <Button variant="ghost" size="sm" asChild>
              <Link to="/profile">
                <UserAvatar photoUrl={photoUrl} displayName={displayName} size={26} />
              </Link>
            </Button>
          </div>
        </header>
        <div className="flex-1 overflow-hidden" key={location.pathname}>
          <Outlet />
        </div>
        <nav className="grid grid-cols-5 border-t md:hidden">
          {NAV.slice(0, 5).map(({ to, key, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                cn(
                  'flex flex-col items-center justify-center py-2 text-[11px]',
                  isActive ? 'text-primary' : 'text-muted-foreground',
                )
              }
            >
              <Icon className="mb-0.5 h-5 w-5" />
              {t(`nav.${key}`)}
            </NavLink>
          ))}
        </nav>
      </main>
    </div>
  );
}
