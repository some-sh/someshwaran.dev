/**
 * Code-based route tree (as opposed to file-based routing + its codegen
 * step) — the officially-supported alternative TanStack Router docs
 * describe for exactly this size of app: a handful of routes, no need
 * for the extra build-time generation step or its generated file.
 *
 * Auth is enforced here, not in the page components: the /admin layout
 * route's beforeLoad redirects to /admin/login when no key is stored,
 * and /admin/login's own beforeLoad redirects the other way when one
 * already is — the same single check (app.core.security.require_admin's
 * frontend counterpart, app/lib/api.ts's getAdminKey) in one place
 * rather than duplicated per page.
 */
import { createRootRoute, createRoute, createRouter, redirect } from '@tanstack/react-router'

import { getAdminKey } from '@/lib/api'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { PublicResumePage } from '@/pages/PublicResumePage'
import { AdminLoginPage } from '@/pages/admin/AdminLoginPage'
import { AdminResumeEditorPage } from '@/pages/admin/AdminResumeEditorPage'
import { AdminResumeListPage } from '@/pages/admin/AdminResumeListPage'

const rootRoute = createRootRoute({
  notFoundComponent: NotFoundPage,
})

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: PublicResumePage,
})

const adminLoginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'admin/login',
  beforeLoad: () => {
    if (getAdminKey()) {
      throw redirect({ to: '/admin' })
    }
  },
  component: AdminLoginPage,
})

// Pathed layout: contributes "/admin" to every child's URL and holds the
// one auth check every admin page needs. No component of its own —
// TanStack Router renders an Outlet by default for a route with children
// and no explicit component.
const adminRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: 'admin',
  beforeLoad: () => {
    if (!getAdminKey()) {
      throw redirect({ to: '/admin/login' })
    }
  },
})

const adminIndexRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: '/',
  component: AdminResumeListPage,
})

const adminNewResumeRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: 'resumes/new',
  component: AdminResumeEditorPage,
})

const adminEditResumeRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: 'resumes/$id',
  component: AdminResumeEditorPage,
})

export const routeTree = rootRoute.addChildren([
  indexRoute,
  adminLoginRoute,
  adminRoute.addChildren([adminIndexRoute, adminNewResumeRoute, adminEditResumeRoute]),
])

export const router = createRouter({ routeTree })

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
