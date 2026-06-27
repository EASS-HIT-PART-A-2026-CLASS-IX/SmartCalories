import { useEffect } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';

import { AppShell } from '@/components/layout/AppShell';
import { AuthProvider } from '@/components/AuthProvider';
import { HealthGate } from '@/components/HealthGate';
import { applyTheme, usePrefsStore } from '@/stores/prefsStore';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, refetchOnWindowFocus: false, retry: 1 },
  },
});

import { ChatView } from '@/features/chat/ChatView';
import DiaryRoute from '@/routes/diary';
import LoginRoute from '@/routes/login';

export default function App() {
  const theme = usePrefsStore((s) => s.theme);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  return (
    <QueryClientProvider client={queryClient}>
      {/* Block the app until the backend answers /health — the free-tier API sleeps when idle
          and needs a cold-start window. HealthGate shows a welcoming "waking up" screen meanwhile. */}
      <HealthGate>
        <AuthProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/login" element={<LoginRoute />} />
              <Route element={<AppShell />}>
                {/* Same `key` forces React to reuse the single ChatView instance when navigating
                    between / and /c/:id, so in-flight streaming state survives the URL change. */}
                <Route index element={<ChatView key="chat" />} />
                <Route path="c/:sessionId" element={<ChatView key="chat" />} />
                <Route path="diary" element={<DiaryRoute />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Route>
            </Routes>
          </BrowserRouter>
          <Toaster richColors position="top-center" />
        </AuthProvider>
      </HealthGate>
    </QueryClientProvider>
  );
}
