import { Link, useNavigate } from '@tanstack/react-router'

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
import { clearAdminKey, downloadAdminExport } from '@/lib/api'
import {
  useAdminResumesQuery,
  useCloneResumeMutation,
  useDeleteResumeMutation,
  useSetDefaultResumeMutation,
} from '@/lib/queries'

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
