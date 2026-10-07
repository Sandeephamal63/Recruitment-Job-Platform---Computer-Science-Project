import api from '@/api/client'
import type { ApiEnvelope } from '@/types/auth'
import type { Job, JobPayload, JobPatch } from '@/types/jobs'

export async function listMyJobs(): Promise<Job[]> {
  const { data } = await api.get<ApiEnvelope<Job[]>>('/jobs/mine')
  return data.data
}

export async function getEmployerOverview(): Promise<{
  openJobs: number
  closedJobs: number
  totalApplicants: number
  shortlisted: number
  averageScore: number | null
}> {
  const { data } = await api.get<ApiEnvelope<{ openJobs: number; closedJobs: number; totalApplicants: number; shortlisted: number; averageScore: number | null }>>('/jobs/mine/overview')
  return data.data
}

/**
 * Funnel stage counts for one job.
 *
 * `underReview` is camelCase because the server maps the `under_review`
 * application status to it (`STAGE_TO_KEY` in `job_service.py`). There is
 * deliberately no `averageScore` here: `StageCountsSchema` declares the field
 * but `_empty_stages` never populates it for this endpoint, so it always
 * serializes as null. Per-job scores live on each application.
 */
export interface JobFunnelEntry {
  jobId: string
  title: string
  status: string
  stages: {
    submitted: number
    underReview: number
    shortlisted: number
    rejected: number
    withdrawn: number
    total: number
  }
}

export async function getEmployerFunnel(): Promise<JobFunnelEntry[]> {
  const { data } = await api.get<ApiEnvelope<JobFunnelEntry[]>>('/jobs/mine/funnel')
  return data.data
}

export async function createJob(payload: JobPayload): Promise<Job> {
  const { data } = await api.post<ApiEnvelope<Job>>('/jobs', payload)
  return data.data
}

export async function getJob(jobId: string): Promise<Job> {
  const { data } = await api.get<ApiEnvelope<Job>>(`/jobs/${jobId}`)
  return data.data
}

export async function updateJob(jobId: string, patch: JobPatch): Promise<Job> {
  const { data } = await api.patch<ApiEnvelope<Job>>(`/jobs/${jobId}`, patch)
  return data.data
}

export async function listOpenJobs(filters: {
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
} = {}): Promise<{ jobs: Job[]; total: number; totalPages: number; hasNext: boolean; hasPrevious: boolean }> {
  const params = new URLSearchParams()
  if (filters.q) params.set('q', filters.q)
  if (filters.location) params.set('location', filters.location)
  if (filters.employmentType) params.set('employmentType', filters.employmentType)
  if (filters.experienceLevel) params.set('experienceLevel', filters.experienceLevel)
  if (filters.remote) params.set('remote', 'true')
  if (filters.salaryMin) params.set('salaryMin', String(filters.salaryMin))
  if (filters.skills?.length) filters.skills.forEach(s => params.append('skills', s))
  if (filters.sort) params.set('sort', filters.sort)
  if (filters.page) params.set('page', String(filters.page))
  if (filters.pageSize) params.set('pageSize', String(filters.pageSize))
  const query = params.toString()
  const { data } = await api.get<ApiEnvelope<Job[]> & { meta?: { pagination: { page: number; pageSize: number; total: number; totalPages: number; hasNext: boolean; hasPrevious: boolean } } }>(`/jobs${query ? `?${query}` : ''}`)
  return {
    jobs: data.data,
    total: data.meta?.pagination?.total ?? data.data.length,
    totalPages: data.meta?.pagination?.totalPages ?? 1,
    hasNext: data.meta?.pagination?.hasNext ?? false,
    hasPrevious: data.meta?.pagination?.hasPrevious ?? false,
  }
}