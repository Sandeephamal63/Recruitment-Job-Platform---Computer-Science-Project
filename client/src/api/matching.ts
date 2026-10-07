import api from '@/api/client'
import type { ApiEnvelope } from '@/types/auth'
import type { CandidateRecommendations, MatchResult } from '@/types/matching'

export async function getMatchResult(applicationId: string): Promise<MatchResult> {
  const { data } = await api.get<ApiEnvelope<MatchResult>>(`/matching/${applicationId}`)
  return data.data
}

export async function listMatchResults(): Promise<MatchResult[]> {
  const { data } = await api.get<ApiEnvelope<MatchResult[]>>('/matching/mine')
  return data.data
}

/**
 * The signed-in candidate's ranked open jobs. Scored by the same pipeline that
 * scores an application, so a job's score here matches the score the employer
 * sees once the candidate applies.
 */
export async function getMyRecommendations(limit?: number): Promise<CandidateRecommendations> {
  const { data } = await api.get<ApiEnvelope<CandidateRecommendations>>(
    '/matching/recommendations',
    { params: limit ? { limit } : undefined },
  )
  return data.data
}

export async function getJobMatchPreview(jobId: string): Promise<MatchResult> {
  const { data } = await api.get<ApiEnvelope<MatchResult>>(`/matching/job/${jobId}/preview`)
  return data.data
}