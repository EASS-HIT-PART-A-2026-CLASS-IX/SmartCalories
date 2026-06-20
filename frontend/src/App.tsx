import { useEffect } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';
import { useTranslation } from 'react-i18next';

import { AppShell } from '@/components/layout/AppShell';
import { AuthProvider } from '@/components/AuthProvider';
import { applyLanguage, applyTheme, usePrefsStore } from '@/stores/prefsStore';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, refetchOnWindowFocus: false, retry: 1 },
  },
});

import { ChatView } from '@/features/chat/ChatView';
import DiaryRoute from '@/routes/diary';
import HistoryRoute from '@/routes/history';
import InsightsRoute from '@/routes/insights';
import LoginRoute from '@/routes/login';
import ProfileRoute from '@/routes/profile';

export default function App() {
  const { i18n } = useTranslation();
  const theme = usePrefsStore((s) => s.theme);
  const language = usePrefsStore((s) => s.language);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  useEffect(() => {
    applyLanguage(language);
    void i18n.changeLanguage(language);
  }, [language, i18n]);

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginRoute />} />
            <Route element={<AppShell />}>
              <Route index element={<ChatView />} />
              <Route path="c/:sessionId" element={<ChatView />} />
              <Route path="diary" element={<DiaryRoute />} />
              <Route path="history" element={<HistoryRoute />} />
              <Route path="insights" element={<InsightsRoute />} />
              <Route path="profile" element={<ProfileRoute />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
        <Toaster richColors position="top-center" />
      </AuthProvider>
    </QueryClientProvider>
  );
}
