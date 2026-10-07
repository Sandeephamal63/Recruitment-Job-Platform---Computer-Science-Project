import api from '@/api/client'
import type { ApiEnvelope, PaginatedResponse } from '@/types/auth'
import type { Application, ApplicationStatus, JobApplicationCount, ApplicationNote } from '@/types/application'
import type { ScoreDistribution } from '@/types/stats'

interface ListApplicantsParams {
  jobId: string
  status?: ApplicationStatus
  minScore?: number
  sort?: 'newest' | 'oldest' | 'score-desc' | 'score-asc'
  page?: number
  pageSize?: number
}

interface ListApplicantsResponse {
  applications: Application[]
  pagination: PaginatedResponse
}

export async function createApplication(jobId: string, cv: File, useProfileCv = false): Promise<Application> {
  const form = new FormData()
  form.append('jobId', jobId)
  if (!useProfileCv) form.append('cv', cv)
  form.append('useProfileCv', String(useProfileCv))
  const { data } = await api.post<ApiEnvelope<Application>>('/applications', form)
  return data.data
}

export async function listMyApplications(): Promise<Application[]> {
  const { data } = await api.get<ApiEnvelope<Application[]>>('/applications/mine')
  return data.data
}

export async function listApplicants(params: ListApplicantsParams): Promise<ListApplicantsResponse> {
  const { jobId, ...filters } = params
  const { data } = await api.get<ApiEnvelope<Application[]>>('/applications', {
    params: { jobId, ...filters },
  })
  return {
    applications: data.data,
    pagination: data.meta?.pagination ?? { page: 1, pageSize: 25, total: data.data.length, totalPages: 1, hasNext: false, hasPrevious: false },
  }
}

export async function getApplication(applicationId: string): Promise<Application> {
  const { data } = await api.get<ApiEnvelope<Application>>(`/applications/${applicationId}`)
  return data.data
}

export async function listApplicationCounts(): Promise<JobApplicationCount[]> {
  const { data } = await api.get<ApiEnvelope<JobApplicationCount[]>>('/applications/counts')
  return data.data
}

export async function updateApplicationStatus(
  applicationId: string,
  status: ApplicationStatus,
  rejectionReason?: string,
): Promise<Application> {
  const { data } = await api.patch<ApiEnvelope<Application>>(`/applications/${applicationId}/status`, { status, rejectionReason })
  return data.data
}

export async function bulkUpdateStatus(
  applicationIds: string[],
  status: ApplicationStatus,
  rejectionReason?: string,
): Promise<{ moved: { id: string; previousStatus: string }[]; skipped: { id: string; reason: string }[]; updated: number }> {
  const { data } = await api.patch<ApiEnvelope<{ moved: { id: string; previousStatus: string }[]; skipped: { id: string; reason: string }[]; updated: number }>>(
    '/applications/bulk-status',
    { applicationIds, status, rejectionReason },
  )
  return data.data
}

export async function withdrawApplication(applicationId: string): Promise<Application> {
  const { data } = await api.post<ApiEnvelope<Application>>(`/applications/${applicationId}/withdraw`)
  return data.data
}

export async function listNotes(applicationId: string): Promise<ApplicationNote[]> {
  const { data } = await api.get<ApiEnvelope<ApplicationNote[]>>(`/applications/${applicationId}/notes`)
  return data.data
}

export async function addNote(applicationId: string, body: string): Promise<ApplicationNote[]> {
  const { data } = await api.post<ApiEnvelope<ApplicationNote[]>>(`/applications/${applicationId}/notes`, { body })
  return data.data
}

export async function removeNote(applicationId: string, noteId: string): Promise<{ removed: string }> {
  const { data } = await api.delete<ApiEnvelope<{ removed: string }>>(`/applications/${applicationId}/notes/${noteId}`)
  return data.data
}

export async function downloadCv(applicationId: string): Promise<Blob> {
  const { data } = await api.get<Blob>(`/applications/${applicationId}/cv`, { responseType: 'blob' })
  return data
}

export async function getEmployerScoreDistribution(): Promise<ScoreDistribution> {
  const { data } = await api.get<ApiEnvelope<ScoreDistribution>>('/applications/scores')
  return data.data
}

export async function getJobScoreDistribution(jobId: string): Promise<ScoreDistribution> {
  const { data } = await api.get<ApiEnvelope<ScoreDistribution>>(`/applications/scores/${jobId}`)
  return data.data
}