import { Fragment, type ReactNode } from 'react'

import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { groupHighlights } from '@/lib/highlights'
import { contactItems } from '@/lib/links'
import type { Resume } from '@/lib/types'

/**
 * The one renderer of a resume on the web: the public page and the admin
 * preview both use it, so what the owner previews is exactly what visitors
 * would see (CLAUDE.md: one model, many renderers). `actions` is the slot
 * for page-specific controls (the public page puts its download buttons there).
 */
export function ResumeView({ resume, actions }: { resume: Resume; actions?: ReactNode }) {
  const info = resume.personal_info
  const contact = info ? contactItems(info) : []
  const skillsByCategory = groupBy(resume.skills, (skill) => skill.category ?? 'General')

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-8 px-4 py-12">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold">{info?.full_name ?? resume.name}</h1>
        {resume.headline && <p className="text-lg font-medium">{resume.headline}</p>}
        {contact.length > 0 && (
          <p className="text-muted-foreground text-sm">
            {contact.map((item, index) => (
              <Fragment key={item.text}>
                {index > 0 && ' • '}
                {item.href ? (
                  <a href={item.href} className="text-foreground underline underline-offset-2">
                    {item.text}
                  </a>
                ) : (
                  item.text
                )}
              </Fragment>
            ))}
          </p>
        )}
        {actions}
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
                {groupHighlights(exp.highlights).map((group, groupIndex) => (
                  <div key={groupIndex} className="mt-2">
                    {group.title && <p className="text-sm font-medium">{group.title}</p>}
                    <ul className="list-disc space-y-1 pl-5 text-sm">
                      {group.bullets.map((bullet, index) => (
                        // Bullets are free text with no stable id; index is fine since
                        // this list is only ever replaced wholesale, never reordered in place.
                        <li key={index}>{bullet}</li>
                      ))}
                    </ul>
                  </div>
                ))}
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
                {formatYears(edu.start_date, edu.end_date) && (
                  <p className="text-muted-foreground text-sm">
                    {formatYears(edu.start_date, edu.end_date)}
                  </p>
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

function groupBy<T>(items: T[], keyFn: (item: T) => string): Record<string, T[]> {
  const result: Record<string, T[]> = {}
  for (const item of items) {
    const key = keyFn(item)
    ;(result[key] ??= []).push(item)
  }
  return result
}

// Pinned to en-US so the page matches the PDF/DOCX exports (see
// backend/app/services/export_service.py) regardless of the visitor's locale.
function formatMonthYear(dateStr: string): string {
  return new Date(`${dateStr}T00:00:00`).toLocaleDateString('en-US', {
    month: 'short',
    year: 'numeric',
  })
}

// Education is shown by year only: the API stores full dates, but a degree's
// month would be a made-up precision (same rule as the exports).
function formatYears(start: string | null, end: string | null): string {
  const startYear = start ? start.slice(0, 4) : ''
  const endYear = end ? end.slice(0, 4) : ''
  if (startYear && endYear && startYear !== endYear) return `${startYear} – ${endYear}`
  return endYear || startYear
}
