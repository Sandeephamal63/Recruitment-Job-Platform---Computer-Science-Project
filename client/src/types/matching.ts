export interface MatchResult {
  applicationId: string
  matchScore: number | null
  matchedSkills: string[]
  missingSkills: string[]
  recommendations: string[]
  modelVersion: string
  createdAt: string | null
}

/**
 * One row of a candidate's proactive job ranking. A match result plus the job it
 * points at, with the two presentation fields denormalized onto the row so a
 * cached ranking renders without a second round trip.
 */
export interface JobRecommendation {
  jobId: string
  matchScore: number
  matchedSkills: string[]
  missingSkills: string[]
  recommendations: string[]
  modelVersion: string
  jobTitle: string
  companyName: string
}

export interface CandidateRecommendations {
  recommendations: JobRecommendation[]
  computedAt: string | null
}