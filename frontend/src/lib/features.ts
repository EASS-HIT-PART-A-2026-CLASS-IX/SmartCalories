/**
 * Centralised feature flags. Trimmed down — surfaces below are off-by-default and only flipped
 * on via env vars when we're actively working on them. Removing the flag means deleting the
 * surface entirely; flagging on a deleted surface is a no-op.
 */

const yes = (v: string | undefined) => v === '1' || v === 'true';

export const features = {
  /** Photo→nutrition multipart upload + Gemini Vision. The rubric "thoughtful enhancement". */
  photoUpload: !(['0', 'false'].includes(import.meta.env.VITE_PHOTO_UPLOAD ?? '')),

  /** /scan slash command in the popover. Off until photo upload UX has a one-tap entry from the popover. */
  scanCommand: yes(import.meta.env.VITE_SCAN_CMD),
} as const;
