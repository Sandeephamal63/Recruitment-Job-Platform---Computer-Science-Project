export interface ScoreBand {
  band: string
  count: number
}

export interface ScoreDistribution {
  buckets: ScoreBand[]
  total: number
}

export interface EmployerOverview {
  openJobs: number
  closedJobs: number
  totalApplicants: number
  shortlisted: number
  averageScore: number | null
}

export interface JobFunnelItem {
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

export interface CandidateScoreDistribution {
  jobId: string
  buckets: ScoreBand[]
  total: number
  average: number | null
}