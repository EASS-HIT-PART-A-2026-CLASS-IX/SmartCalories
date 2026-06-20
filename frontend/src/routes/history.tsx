import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import { ChevronRight, MessageSquare, Trash2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/feedback/EmptyState';
import { ListRowsSkeleton } from '@/components/feedback/Skeletons';
import { deleteConversation, listConversations } from '@/lib/api/chat';

dayjs.extend(relativeTime);

export default function HistoryRoute() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const conversations = useQuery({ queryKey: ['conversations'], queryFn: listConversations });

  const deleteMutation = useMutation({
    mutationFn: deleteConversation,
    onSuccess: (_data, sessionId) => {
      queryClient.setQueryData<{ id: number }[]>(['conversations'], (old) =>
        old ? old.filter((c) => c.id !== sessionId) : [],
      );
      setDeletingId(null);
    },
  });

  return (
    <div className="mx-auto h-full max-w-3xl overflow-y-auto p-6">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Past chats</CardTitle>
          {conversations.data && conversations.data.length > 0 && (
            <span className="text-sm text-muted-foreground">
              {conversations.data.length} conversation{conversations.data.length !== 1 ? 's' : ''}
            </span>
          )}
        </CardHeader>
        <CardContent>
          {conversations.isLoading ? (
            <ListRowsSkeleton rows={6} />
          ) : conversations.data && conversations.data.length === 0 ? (
            <EmptyState description={t('empty.history')} />
          ) : (
            <ul className="divide-y divide-border">
              {conversations.data?.map((c) => (
                <li key={c.id} className="group flex items-center gap-1 py-1">
                  <button
                    type="button"
                    onClick={() => navigate(`/c/${c.id}`)}
                    className="flex flex-1 items-center gap-3 rounded-md p-3 text-start text-sm hover:bg-secondary"
                  >
                    <MessageSquare className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <span className="flex-1 truncate font-medium">
                      {(c.title ?? '').trim() || 'Untitled chat'}
                    </span>
                    <span
                      className="shrink-0 text-xs text-muted-foreground"
                      title={dayjs(c.created_at).format('MMM D, YYYY HH:mm')}
                    >
                      {dayjs(c.created_at).fromNow()}
                    </span>
                    <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
                  </button>
                  {deletingId === c.id ? (
                    <div className="flex shrink-0 items-center gap-1 pr-1">
                      <Button
                        size="sm"
                        variant="destructive"
                        className="h-7 text-xs"
                        disabled={deleteMutation.isPending}
                        onClick={() => deleteMutation.mutate(c.id)}
                      >
                        Delete
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 text-xs"
                        onClick={() => setDeletingId(null)}
                      >
                        Cancel
                      </Button>
                    </div>
                  ) : (
                    <Button
                      size="icon"
                      variant="ghost"
                      className="h-8 w-8 shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
                      onClick={(e) => {
                        e.stopPropagation();
                        setDeletingId(c.id);
                      }}
                      title="Delete conversation"
                    >
                      <Trash2 className="h-4 w-4 text-muted-foreground" />
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
