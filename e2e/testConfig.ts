// Shared between playwright.config.ts (which passes it to the server it
// spawns) and the test files (which need the same value to sign in) —
// one source of truth instead of two places that could drift apart.
export const ADMIN_KEY = process.env.E2E_ADMIN_KEY ?? 'e2e-test-key'
