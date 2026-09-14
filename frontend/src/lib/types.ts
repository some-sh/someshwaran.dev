/**
 * Mirrors backend/app/schemas/resume.py's *Read/*Input schemas — the
 * wire shapes the API actually returns/accepts. Kept as one file since
 * both the public page and the admin editor render/edit the same
 * resume shape, per CLAUDE.md's "one schema" architecture principle.
 */

export interface PersonalInfo {
  id: number
  full_name: string
  email: string
  phone: string | null
  location: string | null
  website: string | null
  github: string | null
  linkedin: string | null
}

export interface Skill {
  id: number
  name: string
  category: string | null
}

export interface Experience {
  id: number
  company: string
  role: string
  location: string | null
  start_date: string // YYYY-MM-DD
  end_date: string | null
  highlights: string[]
}

export interface Project {
  id: number
  name: string
  description: string
  url: string | null
  tech_stack: string[]
}

export interface Education {
  id: number
  institution: string
  degree: string
  field_of_study: string | null
  start_date: string | null
  end_date: string | null
}

export interface Certification {
  id: number
  name: string
  issuer: string | null
  issued_date: string | null
  url: string | null
}

export interface Resume {
  id: number
  name: string
  is_default: boolean
  summary: string
  created_at: string
  updated_at: string
  personal_info: PersonalInfo | null
  skills: Skill[]
  experience: Experience[]
  projects: Project[]
  education: Education[]
  certifications: Certification[]
}

export interface ResumeSummary {
  id: number
  name: string
  is_default: boolean
  created_at: string
  updated_at: string
}

// Input shapes: same fields as their Read counterparts minus `id`
// (server-assigned), used for both create and update payloads.
export type PersonalInfoInput = Omit<PersonalInfo, 'id'>
export type SkillInput = Omit<Skill, 'id'>
export type ExperienceInput = Omit<Experience, 'id'>
export type ProjectInput = Omit<Project, 'id'>
export type EducationInput = Omit<Education, 'id'>
export type CertificationInput = Omit<Certification, 'id'>

export interface ResumeInput {
  name: string
  summary: string
  personal_info: PersonalInfoInput
  skills: SkillInput[]
  experience: ExperienceInput[]
  projects: ProjectInput[]
  education: EducationInput[]
  certifications: CertificationInput[]
}
