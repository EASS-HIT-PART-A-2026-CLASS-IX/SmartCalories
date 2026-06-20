import { useTranslation } from 'react-i18next';
import { Plus } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { Conversation } from '@/lib/api/chat';
import dayjs from 'dayjs';

interface Props {
  conversations: Conversation[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  onNew: () => void;
}

export function ConversationSidebar({ conversations, selectedId, onSelect, onNew }: Props) {
  const { t } = useTranslation();
  return (
    <aside className="hidden w-64 shrink-0 flex-col border-e bg-card/40 lg:flex">
      <div className="p-3">
        <Button variant="outline" className="w-full" onClick={onNew}>
          <Plus className="me-2 h-4 w-4" />
          {t('actions.newChat')}
        </Button>
      </div>
      <div className="flex-1 overflow-y-auto px-2">
        {conversations.length === 0 && (
          <div className="px-3 py-2 text-xs text-muted-foreground">No conversations yet.</div>
        )}
        <ul className="space-y-0.5">
          {conversations.map((c) => (
            <li key={c.id}>
              <button
                type="button"
                onClick={() => onSelect(c.id)}
                className={cn(
                  'flex w-full flex-col gap-0.5 rounded-md px-3 py-2 text-start text-sm transition-colors',
                  selectedId === c.id
                    ? 'bg-accent text-accent-foreground'
                    : 'text-muted-foreground hover:bg-secondary hover:text-foreground',
                )}
              >
                <span className="truncate font-medium">{c.title}</span>
                <span className="text-[10px] opacity-60">{dayjs(c.created_at).format('MMM D, HH:mm')}</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </aside>
  );
}
