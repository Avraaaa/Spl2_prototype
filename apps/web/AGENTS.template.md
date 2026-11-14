# Web-specific instructions
Default to TypeScript strict mode and feature-owned UI modules. Use React hooks and TanStack Query for server state.
Django is the source of truth for permissions; the UI only offers convenience hints.
Generated schema/client files are generated, never hand edited. `npm run --prefix apps/web generate:api` after OpenAPI change.
Use `npm ci --prefix apps/web` and `npm run --prefix apps/web check`; never use Python for frontend tooling.
