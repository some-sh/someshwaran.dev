import { Button } from '@/components/ui/button'

/**
 * Phase 1 scaffolding placeholder.
 *
 * Renders a shadcn/ui Button purely to confirm Tailwind + shadcn/ui are
 * wired up correctly. Real public/admin pages land in later phases per
 * CLAUDE.md's phase plan.
 */
function App() {
  return (
    <main className="flex min-h-svh flex-col items-center justify-center gap-4">
      <h1 className="text-2xl font-medium">someshwaran.dev</h1>
      <Button>shadcn/ui is wired up</Button>
    </main>
  )
}

export default App
