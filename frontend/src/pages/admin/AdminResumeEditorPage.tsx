import { useNavigate, useParams } from '@tanstack/react-router'
import {
  type FormEvent,
  type ReactElement,
  type ReactNode,
  cloneElement,
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
} from 'react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  useAdminResumeQuery,
  useCreateResumeMutation,
  useUpdateResumeMutation,
} from '@/lib/queries'
import type {
  CertificationInput,
  EducationInput,
  ExperienceInput,
  PersonalInfoInput,
  ProjectInput,
  ResumeInput,
  SkillInput,
} from '@/lib/types'

type Keyed<T> = T & { key: string }

function keyed<T>(item: T): Keyed<T> {
  return { ...item, key: crypto.randomUUID() }
}

function stripKey<T extends { key: string }>(item: T): Omit<T, 'key'> {
  const { key, ...rest } = item
  void key // referenced so eslint doesn't flag it as unused
  return rest
}

function useEditableList<T>(initial: T[]) {
  const [items, setItems] = useState<Keyed<T>[]>(() => initial.map(keyed))

  const add = useCallback((blank: T) => setItems((prev) => [...prev, keyed(blank)]), [])
  const update = useCallback(
    (key: string, patch: Partial<T>) =>
      setItems((prev) => prev.map((item) => (item.key === key ? { ...item, ...patch } : item))),
    [],
  )
  const remove = useCallback(
    (key: string) => setItems((prev) => prev.filter((item) => item.key !== key)),
    [],
  )

  return { items, setItems, add, update, remove }
}

type ListApi<T> = ReturnType<typeof useEditableList<T>>

const BLANK_PERSONAL_INFO: PersonalInfoInput = {
  full_name: '',
  email: '',
  phone: null,
  location: null,
  website: null,
  github: null,
  linkedin: null,
}

export function AdminResumeEditorPage() {
  const navigate = useNavigate()
  // Shared between /admin/resumes/new (no id param) and
  // /admin/resumes/$id (id param) — strict:false gives the union of
  // both instead of requiring a `from` tied to just one of them.
  const params = useParams({ strict: false })
  const isEditing = params.id !== undefined
  const resumeId = params.id ? Number(params.id) : null

  const resumeQuery = useAdminResumeQuery(resumeId)
  const createMutation = useCreateResumeMutation()
  const updateMutation = useUpdateResumeMutation(resumeId ?? -1)
  const saveMutation = isEditing ? updateMutation : createMutation

  // Tracks which resume id the form fields currently hold. Needed so a
  // background re-fetch of the same query (TanStack Query's normal
  // behavior) never clobbers in-progress edits — the form is seeded from
  // server data exactly once per id, not on every data change.
  const seededForIdRef = useRef<number | null>(null)

  const [name, setName] = useState('')
  const [summary, setSummary] = useState('')
  const [personalInfo, setPersonalInfo] = useState<PersonalInfoInput>(BLANK_PERSONAL_INFO)

  const skills = useEditableList<SkillInput>([])
  const experience = useEditableList<ExperienceInput>([])
  const projects = useEditableList<ProjectInput>([])
  const education = useEditableList<EducationInput>([])
  const certifications = useEditableList<CertificationInput>([])

  useEffect(() => {
    const resume = resumeQuery.data
    if (resumeId === null || !resume || seededForIdRef.current === resumeId) return
    seededForIdRef.current = resumeId
    setName(resume.name)
    setSummary(resume.summary)
    setPersonalInfo(resume.personal_info ? { ...resume.personal_info } : BLANK_PERSONAL_INFO)
    skills.setItems(resume.skills.map(keyed))
    experience.setItems(resume.experience.map(keyed))
    projects.setItems(resume.projects.map(keyed))
    education.setItems(resume.education.map(keyed))
    certifications.setItems(resume.certifications.map(keyed))
    // The editable-list setters are stable (useCallback, no deps) — only
    // re-seed when the id or the underlying query data actually changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resumeId, resumeQuery.data])

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()

    const payload: ResumeInput = {
      name,
      summary,
      personal_info: personalInfo,
      skills: skills.items.map(stripKey),
      experience: experience.items.map(stripKey),
      projects: projects.items.map(stripKey),
      education: education.items.map(stripKey),
      certifications: certifications.items.map(stripKey),
    }

    const saved = await saveMutation.mutateAsync(payload)
    await navigate({ to: '/admin/resumes/$id', params: { id: String(saved.id) }, replace: true })
  }

  if (isEditing && resumeQuery.isPending) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-10">
        <p className="text-muted-foreground text-sm">Loading…</p>
      </main>
    )
  }

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-10">
      <h1 className="text-2xl font-semibold">{isEditing ? 'Edit resume' : 'New resume'}</h1>

      <form onSubmit={handleSubmit} className="flex flex-col gap-8">
        <Card>
          <CardHeader>
            <CardTitle>Basics</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <Field label="Internal name">
              <Input value={name} onChange={(e) => setName(e.target.value)} required />
            </Field>
            <Field label="Summary">
              <Textarea value={summary} onChange={(e) => setSummary(e.target.value)} rows={4} />
            </Field>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Personal info</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Full name">
              <Input
                value={personalInfo.full_name}
                onChange={(e) => setPersonalInfo((p) => ({ ...p, full_name: e.target.value }))}
                required
              />
            </Field>
            <Field label="Email">
              <Input
                type="email"
                value={personalInfo.email}
                onChange={(e) => setPersonalInfo((p) => ({ ...p, email: e.target.value }))}
                required
              />
            </Field>
            <Field label="Phone">
              <Input
                value={personalInfo.phone ?? ''}
                onChange={(e) => setPersonalInfo((p) => ({ ...p, phone: e.target.value || null }))}
              />
            </Field>
            <Field label="Location">
              <Input
                value={personalInfo.location ?? ''}
                onChange={(e) =>
                  setPersonalInfo((p) => ({ ...p, location: e.target.value || null }))
                }
              />
            </Field>
            <Field label="Website">
              <Input
                value={personalInfo.website ?? ''}
                onChange={(e) =>
                  setPersonalInfo((p) => ({ ...p, website: e.target.value || null }))
                }
              />
            </Field>
            <Field label="GitHub">
              <Input
                value={personalInfo.github ?? ''}
                onChange={(e) => setPersonalInfo((p) => ({ ...p, github: e.target.value || null }))}
              />
            </Field>
            <Field label="LinkedIn">
              <Input
                value={personalInfo.linkedin ?? ''}
                onChange={(e) =>
                  setPersonalInfo((p) => ({ ...p, linkedin: e.target.value || null }))
                }
              />
            </Field>
          </CardContent>
        </Card>

        <SkillsSection list={skills} />
        <ExperienceSection list={experience} />
        <ProjectsSection list={projects} />
        <EducationSection list={education} />
        <CertificationsSection list={certifications} />

        {saveMutation.isError && (
          <p className="text-destructive text-sm">
            {saveMutation.error instanceof Error ? saveMutation.error.message : 'Failed to save'}
          </p>
        )}

        <div className="flex gap-2">
          <Button type="submit" disabled={saveMutation.isPending}>
            {saveMutation.isPending ? 'Saving…' : 'Save'}
          </Button>
          <Button type="button" variant="outline" onClick={() => navigate({ to: '/admin' })}>
            Cancel
          </Button>
        </div>
      </form>
    </main>
  )
}

function Field({ label, children }: { label: string; children: ReactElement<{ id?: string }> }) {
  const id = useId()
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      {cloneElement(children, { id })}
    </div>
  )
}

function SectionCard({
  title,
  onAdd,
  addLabel,
  children,
}: {
  title: string
  onAdd: () => void
  addLabel: string
  children: ReactNode
}) {
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle>{title}</CardTitle>
        <Button type="button" size="sm" variant="outline" onClick={onAdd}>
          {addLabel}
        </Button>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">{children}</CardContent>
    </Card>
  )
}

function RemoveButton({ onClick }: { onClick: () => void }) {
  return (
    <Button type="button" size="sm" variant="ghost" onClick={onClick}>
      Remove
    </Button>
  )
}

function EmptyHint() {
  return <p className="text-muted-foreground text-sm">None yet.</p>
}

function linesToList(value: string): string[] {
  return value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
}

function commaToList(value: string): string[] {
  return value
    .split(',')
    .map((part) => part.trim())
    .filter(Boolean)
}

function SkillsSection({ list }: { list: ListApi<SkillInput> }) {
  return (
    <SectionCard
      title="Skills"
      addLabel="Add skill"
      onAdd={() => list.add({ name: '', category: null })}
    >
      {list.items.length === 0 && <EmptyHint />}
      {list.items.map((item) => (
        <div key={item.key} className="flex flex-wrap items-end gap-2">
          <Field label="Name">
            <Input
              value={item.name}
              onChange={(e) => list.update(item.key, { name: e.target.value })}
              required
            />
          </Field>
          <Field label="Category">
            <Input
              value={item.category ?? ''}
              onChange={(e) => list.update(item.key, { category: e.target.value || null })}
            />
          </Field>
          <RemoveButton onClick={() => list.remove(item.key)} />
        </div>
      ))}
    </SectionCard>
  )
}

function ExperienceSection({ list }: { list: ListApi<ExperienceInput> }) {
  return (
    <SectionCard
      title="Experience"
      addLabel="Add role"
      onAdd={() =>
        list.add({
          company: '',
          role: '',
          location: null,
          start_date: '',
          end_date: null,
          highlights: [],
        })
      }
    >
      {list.items.length === 0 && <EmptyHint />}
      {list.items.map((item) => (
        <div key={item.key} className="flex flex-col gap-3 rounded-md border p-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Field label="Company">
              <Input
                value={item.company}
                onChange={(e) => list.update(item.key, { company: e.target.value })}
                required
              />
            </Field>
            <Field label="Role">
              <Input
                value={item.role}
                onChange={(e) => list.update(item.key, { role: e.target.value })}
                required
              />
            </Field>
            <Field label="Location">
              <Input
                value={item.location ?? ''}
                onChange={(e) => list.update(item.key, { location: e.target.value || null })}
              />
            </Field>
            <Field label="Start date">
              <Input
                type="date"
                value={item.start_date}
                onChange={(e) => list.update(item.key, { start_date: e.target.value })}
                required
              />
            </Field>
            <Field label="End date (blank = present)">
              <Input
                type="date"
                value={item.end_date ?? ''}
                onChange={(e) => list.update(item.key, { end_date: e.target.value || null })}
              />
            </Field>
          </div>
          <Field label="Highlights (one per line)">
            <Textarea
              value={item.highlights.join('\n')}
              onChange={(e) => list.update(item.key, { highlights: linesToList(e.target.value) })}
              rows={4}
            />
          </Field>
          <div>
            <RemoveButton onClick={() => list.remove(item.key)} />
          </div>
        </div>
      ))}
    </SectionCard>
  )
}

function ProjectsSection({ list }: { list: ListApi<ProjectInput> }) {
  return (
    <SectionCard
      title="Projects"
      addLabel="Add project"
      onAdd={() => list.add({ name: '', description: '', url: null, tech_stack: [] })}
    >
      {list.items.length === 0 && <EmptyHint />}
      {list.items.map((item) => (
        <div key={item.key} className="flex flex-col gap-3 rounded-md border p-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Field label="Name">
              <Input
                value={item.name}
                onChange={(e) => list.update(item.key, { name: e.target.value })}
                required
              />
            </Field>
            <Field label="URL">
              <Input
                value={item.url ?? ''}
                onChange={(e) => list.update(item.key, { url: e.target.value || null })}
              />
            </Field>
            <Field label="Tech stack (comma-separated)">
              <Input
                value={item.tech_stack.join(', ')}
                onChange={(e) => list.update(item.key, { tech_stack: commaToList(e.target.value) })}
              />
            </Field>
          </div>
          <Field label="Description">
            <Textarea
              value={item.description}
              onChange={(e) => list.update(item.key, { description: e.target.value })}
              rows={3}
            />
          </Field>
          <div>
            <RemoveButton onClick={() => list.remove(item.key)} />
          </div>
        </div>
      ))}
    </SectionCard>
  )
}

function EducationSection({ list }: { list: ListApi<EducationInput> }) {
  return (
    <SectionCard
      title="Education"
      addLabel="Add education"
      onAdd={() =>
        list.add({
          institution: '',
          degree: '',
          field_of_study: null,
          start_date: null,
          end_date: null,
        })
      }
    >
      {list.items.length === 0 && <EmptyHint />}
      {list.items.map((item) => (
        <div key={item.key} className="grid grid-cols-1 gap-3 rounded-md border p-3 sm:grid-cols-2">
          <Field label="Institution">
            <Input
              value={item.institution}
              onChange={(e) => list.update(item.key, { institution: e.target.value })}
              required
            />
          </Field>
          <Field label="Degree">
            <Input
              value={item.degree}
              onChange={(e) => list.update(item.key, { degree: e.target.value })}
              required
            />
          </Field>
          <Field label="Field of study">
            <Input
              value={item.field_of_study ?? ''}
              onChange={(e) => list.update(item.key, { field_of_study: e.target.value || null })}
            />
          </Field>
          <Field label="End date">
            <Input
              type="date"
              value={item.end_date ?? ''}
              onChange={(e) => list.update(item.key, { end_date: e.target.value || null })}
            />
          </Field>
          <div className="sm:col-span-2">
            <RemoveButton onClick={() => list.remove(item.key)} />
          </div>
        </div>
      ))}
    </SectionCard>
  )
}

function CertificationsSection({ list }: { list: ListApi<CertificationInput> }) {
  return (
    <SectionCard
      title="Certifications"
      addLabel="Add certification"
      onAdd={() => list.add({ name: '', issuer: null, issued_date: null, url: null })}
    >
      {list.items.length === 0 && <EmptyHint />}
      {list.items.map((item) => (
        <div key={item.key} className="grid grid-cols-1 gap-3 rounded-md border p-3 sm:grid-cols-2">
          <Field label="Name">
            <Input
              value={item.name}
              onChange={(e) => list.update(item.key, { name: e.target.value })}
              required
            />
          </Field>
          <Field label="Issuer">
            <Input
              value={item.issuer ?? ''}
              onChange={(e) => list.update(item.key, { issuer: e.target.value || null })}
            />
          </Field>
          <div className="sm:col-span-2">
            <RemoveButton onClick={() => list.remove(item.key)} />
          </div>
        </div>
      ))}
    </SectionCard>
  )
}
