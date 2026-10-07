export const EMPLOYMENT_TYPES = ['full-time', 'part-time', 'contract'] as const
export type EmploymentType = (typeof EMPLOYMENT_TYPES)[number]

export const EXPERIENCE_LEVELS = ['internship', 'entry', 'mid', 'senior', 'lead', 'principal'] as const
export type ExperienceLevel = (typeof EXPERIENCE_LEVELS)[number]

export const CURRENCIES = ['GBP', 'USD', 'EUR'] as const
export type Currency = (typeof CURRENCIES)[number]

export type JobStatus = 'open' | 'closed'

export type { EmployerSummary } from '@/types/profile'

import type { EmployerSummary } from '@/types/profile'

export interface Job {
  id: string
  employerId: string
  title: string
  description: string
  requiredSkills: string[]
  location: string
  employmentType: string
  salaryMin: number | null
  salaryMax: number | null
  currency: string
  experienceLevel: string
  remote: boolean
  status: 'open' | 'closed'
  /** Last day applications are accepted, `YYYY-MM-DD`; `null` = open-ended. */
  deadline: string | null
  applicantCount: number
  employer: EmployerSummary | null
  createdAt: string
  updatedAt: string
  saved?: boolean
}

export interface JobPayload {
  title: string
  description: string
  requiredSkills: string[]
  location: string
  employmentType: string
  salaryMin?: number
  salaryMax?: number
  currency?: string
  experienceLevel?: string
  remote?: boolean
  /** `YYYY-MM-DD`. Omit for an open-ended vacancy. */
  deadline?: string
}

export interface JobFilters {
  q?: string
  location?: string
  employmentType?: string
  experienceLevel?: string
  remote?: boolean
  salaryMin?: number
  skills?: string[]
  sort?: 'newest' | 'oldest' | 'title'
  page?: number
  pageSize?: number
}

export interface PaginatedJobsResponse {
  jobs: Job[]
  total: number
  totalPages: number
  hasNext: boolean
  hasPrevious: boolean
}

export interface JobPayloadWithEmployer extends JobPayload {
  employerId?: string
}

export interface JobPatch {
  title?: string
  description?: string
  requiredSkills?: string[]
  location?: string
  employmentType?: string
  salaryMin?: number
  salaryMax?: number
  currency?: string
  experienceLevel?: string
  remote?: boolean
  status?: JobStatus
  /** `null` withdraws the deadline, returning the posting to open-ended. */
  deadline?: string | null
}