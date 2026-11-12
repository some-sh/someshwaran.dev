import { Link, useParams } from '@tanstack/react-router'
import { type ReactNode, useEffect } from 'react'

import { ResumeView } from '@/components/ResumeView'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useAdminResumeQuery } from '@/lib/queries'

/**
 * Renders any resume (default or not) exactly as the public page would, via
 * the same ResumeView, so a draft can be reviewed before it is published.
 * The data comes from the admin endpoint (the public one only serves the
 * default), so this page is only reachable behind the /admin auth guard.
 */
export function AdminResumePreviewPage() {
  const { id } = useParams({ from: '/admin/resumes/$id/preview' })
  const resumeId = Number(id)
  const query = useAdminResumeQuery(Number.isInteger(resumeId) ? resumeId : null)

  const resume = query.data
  useEffect(() => {
    if (!resume) return
    document.title = `Preview — ${resume.name}`
    return () => {
      document.title = 'someshwaran.dev'
    }
  }, [resume])

  if (query.isPending) return <Message>Loading…</Message>
  if (query.isError) return <Message>Couldn’t load this resume: {query.error.message}</Message>

  return (
    <>
      <div className="bg-muted border-b print:hidden">
        <div className="mx-auto flex max-w-3xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <p className="flex flex-wrap items-center gap-2 text-sm">
            <span className="font-medium">Preview</span>
            <span className="text-muted-foreground [overflow-wrap:anywhere]">
              {query.data.name}
            </span>
            {query.data.is_default ? (
              <Badge>Published (default)</Badge>
            ) : (
              <Badge variant="secondary">Not published</Badge>
            )}
          </p>
          <div className="flex gap-2">
            <Button asChild size="sm" variant="outline">
              <Link to="/admin/resumes/$id" params={{ id }}>
                Edit
              </Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link to="/admin">All resumes</Link>
            </Button>
          </div>
        </div>
      </div>
      <ResumeView resume={query.data} />
    </>
  )
}

function Message({ children }: { children: ReactNode }) {
  return (
    <main className="flex min-h-svh items-center justify-center px-4 text-center">
      <p className="text-muted-foreground">{children}</p>
    </main>
  )
}
