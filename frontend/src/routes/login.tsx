import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Github, Linkedin, LogIn, Sparkles, Wand2 } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { firebaseConfigured } from '@/lib/env';
import { clearFirebaseSession, signInWithGoogle } from '@/lib/firebase';
import { useQueryClient } from '@tanstack/react-query';

import { useAuthStore } from '@/stores/authStore';
import { startDemoSession } from '@/lib/api/domain';

export default function LoginRoute() {
  const navigate = useNavigate();
  const setUser = useAuthStore((s) => s.setUser);
  const setReady = useAuthStore((s) => s.setReady);
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState<string | null>(null);

  const ready = firebaseConfigured();

  const wrap = async (label: string, key: string, fn: () => Promise<void>) => {
    setBusy(key);
    try {
      await fn();
      navigate('/');
    } catch (e) {
      toast.error(`${label} failed: ${e instanceof Error ? e.message : 'unknown'}`);
    } finally {
      setBusy(null);
    }
  };

  const startDemo = async () => {
    const demo = await startDemoSession();
    setUser({
      uid: demo.uid,
      email: demo.email,
      displayName: demo.display_name,
      isAnonymous: demo.is_anonymous,
      idToken: demo.token,
    });
    setReady(true);
    queryClient.clear();
    void clearFirebaseSession();
    toast.success(`Demo loaded — ${demo.seeded.food_entry} diary entries ready`);
  };

  return (
    <div className="flex h-full items-center justify-center bg-background p-6">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="mx-auto mb-2 flex h-12 w-12 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <Sparkles className="h-6 w-6" />
          </div>
          <CardTitle>Welcome to SmartCalories</CardTitle>
          <CardDescription>
            Jump into a fully-loaded demo, or sign in with Google.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Button
            className="w-full"
            variant="secondary"
            onClick={() => wrap('Demo', 'demo', startDemo)}
            disabled={busy !== null}
          >
            <Wand2 className="me-2 h-4 w-4" />
            {busy === 'demo' ? 'Loading demo data…' : 'Explore the demo'}
          </Button>
          <p className="text-center text-[11px] text-muted-foreground">
            Pre-seeded with 30 days of meals and starter chats.
          </p>

          <Separator className="my-3" />

          {!ready ? (
            <div className="rounded-md border border-dashed p-3 text-xs text-muted-foreground">
              Demo mode — set VITE_FB_* in .env.local for real
              <a href="https://firebase.google.com/docs/auth" target="_blank" rel="noreferrer">
                Firebase auth
              </a>
            </div>
          ) : (
            <Button
              className="w-full"
              onClick={() => wrap('Google sign-in', 'google', signInWithGoogle)}
              disabled={busy !== null}
            >
              <LogIn className="me-2 h-4 w-4" />
              Continue with Google
            </Button>
          )}

          <Separator className="my-2" />

          <div className="flex justify-center gap-3 text-muted-foreground">
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
        </CardContent>
      </Card>
    </div>
  );
}
