import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Image as ImageIcon, Send, Square, X } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { matchCommands, SLASH_COMMANDS, type SlashCommand } from '@/lib/slashCommands';
import { SlashCommandPopover } from './SlashCommandPopover';

interface Props {
  disabled?: boolean;
  isStreaming?: boolean;
  onSend: (text: string, file?: File | null) => void;
  onStop?: () => void;
  prefill?: string | null;
  onPrefillConsumed?: () => void;
}

export function Composer({ disabled, isStreaming, onSend, onStop, prefill, onPrefillConsumed }: Props) {
  const { t } = useTranslation();
  const [text, setText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [highlight, setHighlight] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (prefill !== undefined && prefill !== null) {
      setText(prefill);
      requestAnimationFrame(() => {
        textareaRef.current?.focus();
        // Move caret to end so user can immediately add or press Enter.
        const el = textareaRef.current;
        if (el) el.selectionStart = el.selectionEnd = el.value.length;
      });
      onPrefillConsumed?.();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefill]);

  const slashOpen = useMemo(() => /^\/\w*$/.test(text.split('\n')[0] ?? ''), [text]);
  const slashList = useMemo(() => (slashOpen ? matchCommands(text.split(' ')[0]) : SLASH_COMMANDS), [
    slashOpen,
    text,
  ]);

  useEffect(() => setHighlight(0), [text]);

  const submit = () => {
    if (!text.trim() && !file) return;
    onSend(text.trim(), file);
    setText('');
    setFile(null);
  };

  const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (slashOpen && slashList.length) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setHighlight((h) => (h + 1) % slashList.length);
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setHighlight((h) => (h - 1 + slashList.length) % slashList.length);
        return;
      }
      if (e.key === 'Tab' || e.key === 'Enter') {
        if (slashList[highlight]) {
          e.preventDefault();
          insertCommand(slashList[highlight]);
          return;
        }
      }
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const insertCommand = (cmd: SlashCommand) => {
    setText(`/${cmd.name} `);
    requestAnimationFrame(() => textareaRef.current?.focus());
  };


  return (
    <div className="border-t bg-background p-3">
      <div className="relative mx-auto flex max-w-3xl flex-col gap-2 rounded-2xl border bg-card p-2 shadow-sm">
        {file && (
          <div className="flex items-center gap-2 px-2 pt-1">
            <div className="flex items-center gap-2 rounded-md border bg-background px-2 py-1 text-xs">
              <ImageIcon className="h-3 w-3 text-muted-foreground" />
              <span className="max-w-[200px] truncate">{file.name}</span>
              <button
                type="button"
                onClick={() => setFile(null)}
                className="text-muted-foreground hover:text-foreground"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          </div>
        )}

        <Textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKey}
          placeholder="Type a message, or /command, or upload a meal photo…"
          disabled={disabled}
          rows={1}
          className="min-h-[44px] resize-none border-0 bg-transparent px-2 shadow-none focus-visible:ring-0"
        />

        <div className="flex items-center justify-between gap-2 px-1 pb-1">
          <div className="flex items-center gap-1">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              hidden
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={() => fileInputRef.current?.click()}
              disabled={disabled}
              title="Upload meal photo"
            >
              <ImageIcon className="h-4 w-4" />
            </Button>
          </div>

          {isStreaming ? (
            <Button type="button" variant="outline" onClick={onStop}>
              <Square className="me-1 h-3 w-3" />
              {t('actions.stop')}
            </Button>
          ) : (
            <Button type="button" disabled={disabled || (!text.trim() && !file)} onClick={submit}>
              <Send className="me-1 h-3 w-3" />
              {t('actions.send')}
            </Button>
          )}
        </div>

        {slashOpen && slashList.length > 0 && (
          <SlashCommandPopover
            query={text.split(' ')[0] ?? ''}
            highlightIdx={highlight}
            onPick={insertCommand}
          />
        )}
      </div>
    </div>
  );
}
