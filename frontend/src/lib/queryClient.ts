/**
 * One QueryClient for the app. Its queryCache/mutationCache onError is
 * the single place a 401 (revoked/wrong admin key) gets handled —
 * clearing the stored key and bouncing to /admin/login — instead of
 * every page repeating that same try/catch.
 */
import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query'

import { router } from '@/router'

import { ApiError, clearAdminKey } from './api'

function handleQueryError(error: unknown): void {
  if (error instanceof ApiError && error.status === 401) {
    clearAdminKey()
    void router.navigate({ to: '/admin/login', replace: true })
  }
}

export const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: handleQueryError }),
  mutationCache: new MutationCache({ onError: handleQueryError }),
  defaultOptions: {
    queries: {
      // Never worth retrying a 4xx (401/404/422/...) — only genuine
      // network/server errors get a couple of attempts.
      retry: (failureCount, error) =>
        !(error instanceof ApiError && error.status >= 400 && error.status < 500) &&
        failureCount < 2,
    },
  },
})
