import type { Job } from '@/types/jobs'
import type { EmployerSummary } from '@/types/profile'
import type { MatchResult } from '@/types/matching'

export type ApplicationStatus = 'submitted' | 'under_review' | 'shortlisted' | 'rejected' | 'withdrawn'

export interface CandidateProfile {
  id: string
  name: string | null
  headline: string | null
  email: string | null
  skills: string[] | null
}

export interface ApplicationNote {
  id: string
  body: string
  authorUserId: string
  authorName: string
  createdAt: string
}

export interface Application {
  id: string
  jobId: string
  candidateId: string
  employerId: string | null
  status: ApplicationStatus
  rejectionReason: string | null
  notes: ApplicationNote[]
  submittedAt: string
  createdAt: string
  updatedAt: string
  job: Job
  employer: EmployerSummary | null
  cvFileName?: string
  candidate?: CandidateProfile
  match?: MatchResult
}

export interface JobApplicationCount {
  jobId: string
  count: number
}

export type { MatchResult } from '@/types/matching'

export const CV_SIZE_LIMIT_BYTES = 5 * 1024 * 1024