import { useEffect, useRef, useState } from 'react';
import { Send, Square } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';

interface Props {
  disabled?: boolean;
  isStreaming?: boolean;
  onSend: (text: string) => void;
  onStop?: () => void;
  prefill?: string | null;
  onPrefillConsumed?: () => void;
}

export function Composer({ disabled, isStreaming, onSend, onStop, prefill, onPrefillConsumed }: Props) {
  const [text, setText] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

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

  const submit = () => {
    // Don't allow a second send (via Enter) while one is already in flight.
    if (isStreaming) return;
    if (!text.trim()) return;
    onSend(text.trim());
    setText('');
  };

  const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="border-t bg-background p-3">
      <div className="relative mx-auto flex max-w-4xl flex-col gap-2 rounded-2xl border-2 border-foreground/25 bg-card p-2 shadow-sm">
        <Textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKey}
          placeholder="Type a message…"
          disabled={disabled}
          rows={1}
          className="min-h-[44px] resize-none border-0 bg-transparent px-2 shadow-none focus-visible:ring-0"
        />

        <div className="flex items-center justify-end gap-2 px-1 pb-1">
          {isStreaming ? (
            <Button type="button" variant="outline" onClick={onStop}>
              <Square className="me-1 h-3 w-3" />
              Stop
            </Button>
          ) : (
            <Button type="button" disabled={disabled || !text.trim()} onClick={submit}>
              <Send className="me-1 h-3 w-3" />
              Send
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
