# Lighthouse frontend

Next.js 16 and React 19 interface for the Lighthouse Baltimore planning demo.

```bash
npm ci
npm run dev
```

Open http://localhost:3000. Start the FastAPI backend on port 8000, or run `../dev.sh` to start both services. The default `/api` proxy works without an environment file. See `.env.local.example` for optional upstream overrides.

The main flow is situation input → editable review → strategy comparison → actionable timeline → resource details → availability change → replanning. The assistant is a presentation component with a replaceable visual. Resource actions and status changes use the backend's structured data.

Check with `npm run lint`, `npx tsc --noEmit` and `npm run build`. The root README covers demo steps, architecture, data provenance and limitations.
