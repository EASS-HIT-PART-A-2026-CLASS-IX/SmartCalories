# SmartCalories — frontend

Vite + React 18 + TypeScript + Tailwind + shadcn/ui + Firebase Auth + TanStack Query, with
react-i18next (English + Hebrew, RTL). Talks to the FastAPI backend over HTTP + a chat WebSocket.

## Run
```bash
npm install
npm run dev        # http://localhost:5173
```
Config via `.env` (copy from `.env.example` if present): `VITE_API_BASE` (default
`http://localhost:9000`) and the `VITE_FB_*` Firebase keys. Without Firebase keys the app still
runs; sign-in/guest mode needs them.

```bash
npm run build      # tsc + vite build
npm run typecheck  # tsc -b --noEmit
```

In Docker the whole stack (api + web + redis) comes up via `backend/compose.yaml` — see
`../docs/runbooks/compose.md`.

## AI Assistance
Built with Claude Code. Prompts, design decisions, and verification steps are documented in the
root `../README.md` and `../docs/EX3-notes.md`. Outputs were verified locally with `npm run build`
/ `npm run typecheck` and the end-to-end `../scripts/demo.sh`.
