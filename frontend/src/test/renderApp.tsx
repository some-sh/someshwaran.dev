/**
 * Shared test helper: renders through the REAL route tree (router.tsx)
 * with a fresh memory history and a fresh QueryClient per call — this
 * exercises real beforeLoad guards and real navigation, not a
 * hand-rolled stand-in router per test file.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider, createMemoryHistory, createRouter } from '@tanstack/react-router'
import { type RenderResult, render } from '@testing-library/react'

import { routeTree } from '@/router'

export function renderApp(initialPath = '/'): RenderResult {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: [initialPath] }),
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}
