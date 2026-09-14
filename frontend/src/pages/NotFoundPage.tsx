import { Link } from '@tanstack/react-router'

export function NotFoundPage() {
  return (
    <main className="flex min-h-svh flex-col items-center justify-center gap-4 px-4 text-center">
      <p className="text-muted-foreground">Page not found.</p>
      <Link to="/" className="underline underline-offset-4">
        Back home
      </Link>
    </main>
  )
}
