import { features } from './features';

export interface SlashCommand {
  name: string;
  argHint?: string;
  descriptionKey: string;
}

const ALL_COMMANDS: SlashCommand[] = [
  { name: 'log', argHint: '<food> <kcal> [meal]', descriptionKey: 'slash.log' },
  { name: 'macros', descriptionKey: 'slash.macros' },
  { name: 'budget', descriptionKey: 'slash.budget' },
  { name: 'water', argHint: '+1 | <ml>', descriptionKey: 'slash.water' },
  { name: 'goal', argHint: '<kcal>', descriptionKey: 'slash.goal' },
  // Flag-gated; ships when scan UX is one-tap and reliable.
  { name: 'scan', descriptionKey: 'slash.scan' },
];

const HIDDEN: ReadonlySet<string> = new Set(
  [!features.scanCommand && 'scan'].filter(Boolean) as string[],
);

export const SLASH_COMMANDS: SlashCommand[] = ALL_COMMANDS.filter((c) => !HIDDEN.has(c.name));

export function matchCommands(prefix: string): SlashCommand[] {
  const q = prefix.replace(/^\//, '').toLowerCase();
  if (!q) return SLASH_COMMANDS;
  return SLASH_COMMANDS.filter((c) => c.name.startsWith(q));
}
