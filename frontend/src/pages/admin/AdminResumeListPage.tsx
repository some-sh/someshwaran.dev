import { Link, useNavigate } from '@tanstack/react-router'
import { type ChangeEvent, useRef, useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { ApiError, clearAdminKey, downloadAdminExport, downloadBackup } from '@/lib/api'
import {
  useAdminResumesQuery,
  useCloneResumeMutation,
  useDeleteResumeMutation,
  useRestoreBackupMutation,
  useSetDefaultResumeMutation,
} from '@/lib/queries'

/** Download every resume as one file, and restore from such a file. A resume
 * lives in a single database, so a copy you keep elsewhere is the safety net. */
function BackupPanel({ resumeCount }: { resumeCount: number }) {
  const restore = useRestoreBackupMutation()
  const fileInput = useRef<HTMLInputElement>(null)
  const [replace, setReplace] = useState(false)
  const [message, setMessage] = useState<{ kind: 'ok' | 'error'; text: string } | null>(null)

  async function handleDownload() {
    setMessage(null)
    try {
      await downloadBackup()
    } catch (error) {
      setMessage({
        kind: 'error',
        text: error instanceof Error ? error.message : 'Download failed',
      })
    }
  }

  async function handleFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = '' // allow choosing the same file again
    if (!file) return
    setMessage(null)

    let backup: unknown
    try {
      backup = JSON.parse(await file.text())
    } catch {
      setMessage({ kind: 'error', text: "That file isn't valid JSON." })
      return
    }
    if (
      replace &&
      !window.confirm(
        `Replace everything? This deletes all ${resumeCount} existing resume${resumeCount === 1 ? '' : 's'} and restores only what is in the file.`,
      )
    ) {
      return
    }

    try {
      const result = await restore.mutateAsync({ backup, replace })
      const skipped = result.skipped.length
      setMessage({
        kind: 'ok',
        text:
          `Restored ${result.created.length} resume${result.created.length === 1 ? '' : 's'}` +
          (skipped > 0
            ? `; skipped ${skipped} that already exist (${result.skipped.join(', ')})`
            : '') +
          '.',
      })
    } catch (error) {
      setMessage({
        kind: 'error',
        text:
          error instanceof ApiError || error instanceof Error
            ? `Nothing was changed. ${error.message}`
            : 'Restore failed. Nothing was changed.',
      })
    }
  }

  return (
    <section className="flex flex-col gap-3 rounded-md border p-4" aria-label="Backup">
      <div>
        <h2 className="font-medium">Backup</h2>
        <p className="text-muted-foreground text-sm">
          Keep a copy of every resume as one file. Restoring skips resumes whose name already exists
          and never changes which one is published.
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="outline" onClick={handleDownload}>
          Download backup
        </Button>
        <Button
          variant="outline"
          onClick={() => fileInput.current?.click()}
          disabled={restore.isPending}
        >
          Restore from file…
        </Button>
        <input
          ref={fileInput}
          type="file"
          accept="application/json,.json"
          className="hidden"
          aria-label="Backup file"
          onChange={handleFile}
        />
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={replace} onChange={(e) => setReplace(e.target.checked)} />
          Replace all existing resumes
        </label>
      </div>
      {message && (
        <p
          role={message.kind === 'error' ? 'alert' : 'status'}
          className={message.kind === 'error' ? 'text-destructive text-sm' : 'text-sm'}
        >
          {message.text}
        </p>
      )}
    </section>
  )
}

export function AdminResumeListPage() {
  const navigate = useNavigate()
  const resumesQuery = useAdminResumesQuery()
  const setDefaultMutation = useSetDefaultResumeMutation()
  const cloneMutation = useCloneResumeMutation()
  const deleteMutation = useDeleteResumeMutation()

  function handleDelete(id: number, name: string) {
    if (!window.confirm(`Delete "${name}"? This can't be undone.`)) return
    deleteMutation.mutate(id)
  }

  async function handleLogOut() {
    clearAdminKey()
    await navigate({ to: '/admin/login', replace: true })
  }

  const mutationFailed =
    setDefaultMutation.isError || cloneMutation.isError || deleteMutation.isError

  const header = (
    <div className="flex items-center justify-between gap-4">
      <h1 className="text-2xl font-semibold">Resumes</h1>
      <div className="flex gap-2">
        <Button asChild>
          <Link to="/admin/resumes/new">New resume</Link>
        </Button>
        <Button variant="outline" onClick={handleLogOut}>
          Log out
        </Button>
      </div>
    </div>
  )

  if (resumesQuery.isPending) {
    return (
      <main className="mx-auto flex max-w-4xl flex-col gap-6 px-4 py-10">
        {header}
        <p className="text-muted-foreground text-sm">Loading…</p>
      </main>
    )
  }

  if (resumesQuery.isError) {
    return (
      <main className="mx-auto flex max-w-4xl flex-col gap-6 px-4 py-10">
        {header}
        <p className="text-destructive text-sm">
          {resumesQuery.error instanceof Error
            ? resumesQuery.error.message
            : 'Failed to load resumes'}
        </p>
      </main>
    )
  }

  const resumes = resumesQuery.data

  return (
    <main className="mx-auto flex max-w-4xl flex-col gap-6 px-4 py-10">
      {header}

      {mutationFailed && (
        <p className="text-destructive text-sm">Something went wrong — try again.</p>
      )}

      <BackupPanel resumeCount={resumes.length} />

      {resumes.length === 0 ? (
        <p className="text-muted-foreground text-sm">No resumes yet — create one to get started.</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Updated</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {resumes.map((resume) => (
              <TableRow key={resume.id}>
                <TableCell>
                  <Link
                    to="/admin/resumes/$id"
                    params={{ id: String(resume.id) }}
                    className="underline underline-offset-4"
                  >
                    {resume.name}
                  </Link>
                </TableCell>
                <TableCell>{resume.is_default && <Badge>Default</Badge>}</TableCell>
                <TableCell>{new Date(resume.updated_at).toLocaleString()}</TableCell>
                <TableCell>
                  <div className="flex flex-wrap justify-end gap-2">
                    {!resume.is_default && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setDefaultMutation.mutate(resume.id)}
                      >
                        Set default
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => cloneMutation.mutate(resume.id)}
                    >
                      Clone
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => downloadAdminExport(resume.id, 'pdf', resume.name)}
                    >
                      PDF
                    </Button>
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => handleDelete(resume.id, resume.name)}
                    >
                      Delete
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </main>
  )
}
