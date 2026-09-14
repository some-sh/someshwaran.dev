import { type ReactNode } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { ApiError, defaultResumeExportUrl } from '@/lib/api'
import { useDefaultResumeQuery } from '@/lib/queries'

export function PublicResumePage() {
  const query = useDefaultResumeQuery()

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

  const resume = query.data
  const info = resume.personal_info
  const contactParts = info
    ? [info.email, info.phone, info.location, info.website, info.github, info.linkedin].filter(
        (part): part is string => Boolean(part),
      )
    : []
  const skillsByCategory = groupBy(resume.skills, (skill) => skill.category ?? 'General')

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-8 px-4 py-12">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold">{info?.full_name ?? resume.name}</h1>
        {contactParts.length > 0 && (
          <p className="text-muted-foreground text-sm">{contactParts.join(' • ')}</p>
        )}
        <div className="flex gap-2 pt-2">
          <Button asChild variant="outline" size="sm">
            <a href={defaultResumeExportUrl('pdf')}>Download PDF</a>
          </Button>
          <Button asChild variant="outline" size="sm">
            <a href={defaultResumeExportUrl('docx')}>Download DOCX</a>
          </Button>
        </div>
      </header>

      {resume.summary && (
        <section>
          <p>{resume.summary}</p>
        </section>
      )}

      {resume.skills.length > 0 && (
        <Section title="Skills">
          <div className="flex flex-col gap-2">
            {Object.entries(skillsByCategory).map(([category, skills]) => (
              <div key={category} className="flex flex-wrap items-baseline gap-2">
                <span className="text-sm font-medium">{category}:</span>
                {skills.map((skill) => (
                  <Badge key={skill.id} variant="secondary">
                    {skill.name}
                  </Badge>
                ))}
              </div>
            ))}
          </div>
        </Section>
      )}

      {resume.experience.length > 0 && (
        <Section title="Experience">
          <div className="flex flex-col gap-6">
            {resume.experience.map((exp) => (
              <div key={exp.id}>
                <div className="flex flex-wrap items-baseline justify-between gap-x-4">
                  <p className="font-medium">
                    {exp.role}, {exp.company}
                  </p>
                  <p className="text-muted-foreground text-sm">
                    {formatMonthYear(exp.start_date)} –{' '}
                    {exp.end_date ? formatMonthYear(exp.end_date) : 'Present'}
                  </p>
                </div>
                {exp.location && <p className="text-muted-foreground text-sm">{exp.location}</p>}
                {exp.highlights.length > 0 && (
                  <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
                    {exp.highlights.map((highlight, index) => (
                      // Highlights are free-text with no stable id; index is fine
                      // since this list is only ever replaced wholesale, never reordered in place.
                      <li key={index}>{highlight}</li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}

      {resume.projects.length > 0 && (
        <Section title="Projects">
          <div className="flex flex-col gap-4">
            {resume.projects.map((project) => (
              <div key={project.id}>
                <p className="font-medium">
                  {project.url ? (
                    <a
                      href={project.url}
                      className="underline underline-offset-4"
                      target="_blank"
                      rel="noreferrer"
                    >
                      {project.name}
                    </a>
                  ) : (
                    project.name
                  )}
                  {project.tech_stack.length > 0 && (
                    <span className="text-muted-foreground font-normal">
                      {' '}
                      — {project.tech_stack.join(', ')}
                    </span>
                  )}
                </p>
                {project.description && <p className="text-sm">{project.description}</p>}
              </div>
            ))}
          </div>
        </Section>
      )}

      {resume.education.length > 0 && (
        <Section title="Education">
          <div className="flex flex-col gap-2">
            {resume.education.map((edu) => (
              <div key={edu.id} className="flex flex-wrap items-baseline justify-between gap-x-4">
                <p className="font-medium">
                  {edu.degree}, {edu.institution}
                  {edu.field_of_study && (
                    <span className="text-muted-foreground font-normal">
                      {' '}
                      — {edu.field_of_study}
                    </span>
                  )}
                </p>
                {edu.end_date && (
                  <p className="text-muted-foreground text-sm">{formatMonthYear(edu.end_date)}</p>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}

      {resume.certifications.length > 0 && (
        <Section title="Certifications">
          <div className="flex flex-col gap-1">
            {resume.certifications.map((cert) => (
              <p key={cert.id} className="text-sm">
                {cert.name}
                {cert.issuer && <span className="text-muted-foreground"> — {cert.issuer}</span>}
              </p>
            ))}
          </div>
        </Section>
      )}
    </main>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-lg font-semibold">{title}</h2>
      <Separator />
      {children}
    </section>
  )
}

function CenteredMessage({ children }: { children: ReactNode }) {
  return (
    <main className="flex min-h-svh items-center justify-center px-4 text-center">
      <p className="text-muted-foreground">{children}</p>
    </main>
  )
}

function groupBy<T>(items: T[], keyFn: (item: T) => string): Record<string, T[]> {
  const result: Record<string, T[]> = {}
  for (const item of items) {
    const key = keyFn(item)
    ;(result[key] ??= []).push(item)
  }
  return result
}

function formatMonthYear(dateStr: string): string {
  return new Date(`${dateStr}T00:00:00`).toLocaleDateString(undefined, {
    month: 'short',
    year: 'numeric',
  })
}
