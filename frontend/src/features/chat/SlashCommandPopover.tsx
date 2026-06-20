import { useTranslation } from 'react-i18next';
import { matchCommands, SLASH_COMMANDS, type SlashCommand } from '@/lib/slashCommands';
import { cn } from '@/lib/utils';

interface Props {
  query: string;
  highlightIdx: number;
  onPick: (cmd: SlashCommand) => void;
}

export function SlashCommandPopover({ query, highlightIdx, onPick }: Props) {
  const { t } = useTranslation();
  const list = query.startsWith('/') ? matchCommands(query) : SLASH_COMMANDS;
  if (!list.length) return null;

  return (
    <div className="absolute bottom-full start-0 z-50 mb-2 w-80 rounded-lg border bg-card text-card-foreground shadow-lg">
      <div className="px-3 py-2 text-xs font-medium text-muted-foreground">Slash commands</div>
      <ul className="max-h-72 overflow-y-auto pb-1">
        {list.map((cmd, idx) => {
          const isActive = idx === highlightIdx;
          return (
            <li key={cmd.name}>
              <button
                type="button"
                onClick={() => onPick(cmd)}
                className={cn(
                  'flex w-full flex-col gap-0.5 px-3 py-2 text-start transition-colors',
                  isActive ? 'bg-accent text-accent-foreground' : 'hover:bg-accent/50',
                )}
              >
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm font-medium">/{cmd.name}</span>
                  {cmd.argHint && (
                    <span className="font-mono text-xs text-muted-foreground">{cmd.argHint}</span>
                  )}
                </div>
                <span
                  className={cn(
                    'text-xs text-muted-foreground transition-all',
                    isActive ? '' : 'line-clamp-1',
                  )}
                >
                  {t(cmd.descriptionKey)}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
