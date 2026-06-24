import { useEffect, useState } from 'react';
import {
  Link,
  NavLink,
  Outlet,
  useLocation,
  useMatch,
  useNavigate,
} from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import {
  ChevronLeft,
  ChevronRight,
  Github,
  KeyRound,
  LayoutDashboard,
  Linkedin,
  LogOut,
  MessageCircle,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Search,
  Sparkles,
  Sun,
} from 'lucide-react';

import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { Badge } from '@/components/ui/badge';
import { useAuthStore } from '@/stores/authStore';
import { useUiStore } from '@/stores/uiStore';
import { usePrefsStore } from '@/stores/prefsStore';
import { UserAvatar } from '@/components/UserAvatar';
import { useLogout } from '@/hooks/useLogout';
import { useConversations } from '@/hooks/useConversations';
import { searchConversations, type Conversation } from '@/lib/api/chat';
import { ApiKeyDialog } from '@/features/settings/ApiKeyDialog';

const RECENTS_PAGE = 5;

type NavItem = { to: string; key: string; icon: React.ComponentType<{ className?: string }> };

// Bottom tab bar on mobile. Conversations ("Recents") live in the desktop sidebar only.
const MOBILE_NAV: NavItem[] = [
  { to: '/', key: 'chat', icon: MessageCircle },
  { to: '/diary', key: 'diary', icon: LayoutDashboard },
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

  // Conversation list ("Recents") now lives in the main sidebar. selectedId comes from the URL.
  const conversations = useConversations();
  const chatMatch = useMatch('/c/:sessionId');
  const selectedSessionId = chatMatch?.params.sessionId
    ? Number(chatMatch.params.sessionId)
    : null;
  const onNewChat = () => navigate('/');

  const setTheme = usePrefsStore((s) => s.setTheme);
  const theme = usePrefsStore((s) => s.theme);
  const isDark =
    theme === 'dark' ||
    (theme === 'system' &&
      typeof window !== 'undefined' &&
      window.matchMedia('(prefers-color-scheme: dark)').matches);

  const [apiKeyOpen, setApiKeyOpen] = useState(false);

  // Chat search: debounced; when non-empty we show server-side results instead of recents.
  const [searchInput, setSearchInput] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [recentsLimit, setRecentsLimit] = useState(RECENTS_PAGE);
  useEffect(() => {
    const id = setTimeout(() => setSearchTerm(searchInput.trim()), 250);
    return () => clearTimeout(id);
  }, [searchInput]);

  const search = useQuery({
    queryKey: ['conversations', 'search', searchTerm],
    queryFn: () => searchConversations(searchTerm),
    enabled: searchTerm.length > 0,
    staleTime: 30_000,
  });

  const isSearching = searchTerm.length > 0;
  const allRecents: Conversation[] = conversations.data ?? [];
  const recentsList: Conversation[] = isSearching
    ? search.data ?? []
    : allRecents.slice(0, recentsLimit);
  const hasMoreRecents = !isSearching && allRecents.length > recentsLimit;

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
        <nav className="flex flex-1 flex-col gap-1 overflow-y-auto p-2">
          {/* New chat — navigates to the empty hero. Active when we're on `/`. */}
          <button
            type="button"
            onClick={onNewChat}
            title={navCollapsed ? t('actions.newChat') : undefined}
            className={cn(
              'flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors',
              navCollapsed && 'justify-center px-2',
              location.pathname === '/'
                ? 'bg-accent text-accent-foreground font-medium'
                : 'text-muted-foreground hover:bg-secondary hover:text-foreground',
            )}
          >
            <Plus className="h-5 w-5" />
            {!navCollapsed && <span>{t('actions.newChat')}</span>}
          </button>

          {/* Diary */}
          <NavLink
            to="/diary"
            title={navCollapsed ? t('nav.diary') : undefined}
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
            <LayoutDashboard className="h-5 w-5" />
            {!navCollapsed && <span>{t('nav.diary')}</span>}
          </NavLink>

          {/* Recents — search + the conversation list (desktop expanded sidebar only). */}
          {!navCollapsed && (
            <>
              {/* Search chats: matches full message content (user + agent), newest-first. */}
              <div className="relative mt-4 px-1">
                <Search className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="search"
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  placeholder={t('nav.searchChats')}
                  className="w-full rounded-md border bg-background py-1.5 ps-9 pe-3 text-sm outline-none focus-visible:ring-1 focus-visible:ring-ring"
                />
              </div>

              <div className="px-3 pb-1 pt-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {t('nav.recents')}
              </div>

              {isSearching && search.isLoading ? (
                <div className="px-3 py-1 text-xs text-muted-foreground">{t('loading')}</div>
              ) : recentsList.length === 0 ? (
                <div className="px-3 py-1 text-xs text-muted-foreground">
                  {isSearching ? 'No matching chats.' : t('empty.history')}
                </div>
              ) : (
                <>
                  <ul className="space-y-0.5">
                    {recentsList.map((c) => (
                      <li key={c.id}>
                        <button
                          type="button"
                          onClick={() => navigate(`/c/${c.id}`)}
                          title={c.title}
                          className={cn(
                            'w-full truncate rounded-md px-3 py-1.5 text-start text-sm transition-colors',
                            selectedSessionId === c.id
                              ? 'bg-accent text-accent-foreground font-medium'
                              : 'text-muted-foreground hover:bg-secondary hover:text-foreground',
                          )}
                        >
                          {c.title?.trim() || 'Untitled chat'}
                        </button>
                      </li>
                    ))}
                  </ul>
                  {hasMoreRecents && (
                    <button
                      type="button"
                      onClick={() => setRecentsLimit((n) => n + RECENTS_PAGE)}
                      className="mt-1 w-full rounded-md px-3 py-1.5 text-start text-xs font-medium text-primary hover:bg-secondary"
                    >
                      {t('nav.loadMore')}
                    </button>
                  )}
                </>
              )}
            </>
          )}
        </nav>
        <Separator />
        <div className={cn('flex flex-col gap-2 p-3 text-xs', navCollapsed && 'items-center')}>
          {/* Controls — API key + dark mode sit ABOVE the account/email block. */}
          {!navCollapsed && (
            <>
              {/* Personal Gemini API key — only for real signed-in users (not guests). */}
              {!isAnonymous && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setApiKeyOpen(true)}
                  className="justify-start text-muted-foreground"
                >
                  <KeyRound className="me-2 h-3.5 w-3.5" />
                  {t('nav.apiKey')}
                </Button>
              )}
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setTheme(isDark ? 'light' : 'dark')}
                className="justify-start text-muted-foreground"
              >
                {isDark ? (
                  <Sun className="me-2 h-3.5 w-3.5" />
                ) : (
                  <Moon className="me-2 h-3.5 w-3.5" />
                )}
                {t('nav.darkMode')}
              </Button>
              <Separator className="my-1" />
            </>
          )}

          {/* Account block (avatar + name + email). */}
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
          <div className="ms-auto flex items-center gap-2">
            {isAnonymous && (
              <Button variant="outline" size="sm" asChild>
                <Link to="/login">{t('actions.signIn')}</Link>
              </Button>
            )}
            <UserAvatar photoUrl={photoUrl} displayName={displayName} size={26} />
          </div>
        </header>
        <div className="flex-1 overflow-hidden" key={location.pathname}>
          <Outlet />
        </div>
        <nav className="grid grid-cols-2 border-t md:hidden">
          {MOBILE_NAV.map(({ to, key, icon: Icon }) => (
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

      <ApiKeyDialog open={apiKeyOpen} onClose={() => setApiKeyOpen(false)} />
    </div>
  );
}
