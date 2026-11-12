import { type ReactNode, useEffect } from 'react'

import { ResumeView } from '@/components/ResumeView'
import { Button } from '@/components/ui/button'
import { ApiError, defaultResumeExportUrl } from '@/lib/api'
import { useDefaultResumeQuery } from '@/lib/queries'

export function PublicResumePage() {
  const query = useDefaultResumeQuery()

  // The browser tab / search-result title: "Name — Headline" once loaded.
  const loaded = query.data
  useEffect(() => {
    if (!loaded) return
    const name = loaded.personal_info?.full_name ?? loaded.name
    document.title = loaded.headline ? `${name} — ${loaded.headline}` : name
    return () => {
      document.title = 'someshwaran.dev'
    }
  }, [loaded])

  if (query.isPending) {
    return <CenteredMessage>Loading…</CenteredMessage>
  }
  if (query.isError) {
    const { error } = query
    if (error instanceof ApiError && error.status === 404) {
      return <CenteredMessage>No resume has been published yet.</CenteredMessage>
    }
    return <CenteredMessage>Couldn’t load the resume: {error.message}</CenteredMessage>
  }

  return (
    <ResumeView
      resume={query.data}
      actions={
        <div className="flex gap-2 pt-2 print:hidden">
          <Button asChild variant="outline" size="sm">
            <a href={defaultResumeExportUrl('pdf')}>Download PDF</a>
          </Button>
          <Button asChild variant="outline" size="sm">
            <a href={defaultResumeExportUrl('docx')}>Download DOCX</a>
          </Button>
        </div>
      }
    />
  )
}

function CenteredMessage({ children }: { children: ReactNode }) {
  return (
    <main className="flex min-h-svh items-center justify-center px-4 text-center">
      <p className="text-muted-foreground">{children}</p>
    </main>
  )
}
