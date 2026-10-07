import { useEffect, useState } from 'react'
import { listOpenJobs } from '@/api/jobs'
import { getErrorMessage } from '@/api/errors'
import type { EmployerSummary, Job } from '@/types/jobs'

/** How many roles the "latest roles" section shows. */
const FEATURED_JOB_LIMIT = 6

/** Fetched once and shared, so the two landing sections are not two requests. */
const PAGE_SIZE = 24

interface LandingJobs {
  jobs: Job[]
  /** Distinct employers behind those jobs, in first-seen order. */
  employers: EmployerSummary[]
  loading: boolean
  error: string | null
  retry: () => void
}

/**
 * Real, public job data for the landing page.
 *
 * The two sections that need it — the roles list and the employer strip — read
 * the same one page of open jobs, so it is fetched here once and passed down.
 * The strip's employers are derived by de-duplicating `job.employer`, which means
 * only companies with a live opening appear: social proof, not invented logos.
 */
export function useLandingJobs(): LandingJobs {
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)

    listOpenJobs({ sort: 'newest', pageSize: PAGE_SIZE })
      .then((result) => {
        if (active) setJobs(result.jobs)
      })
      .catch((err: unknown) => {
        if (active) setError(getErrorMessage(err))
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [attempt])

  return {
    jobs: jobs.slice(0, FEATURED_JOB_LIMIT),
    employers: distinctEmployers(jobs),
    loading,
    error,
    retry: () => setAttempt((value) => value + 1),
  }
}

function distinctEmployers(jobs: Job[]): EmployerSummary[] {
  const byId = new Map<string, EmployerSummary>()
  for (const job of jobs) {
    if (job.employer && !byId.has(job.employer.id)) {
      byId.set(job.employer.id, job.employer)
    }
  }
  return [...byId.values()]
}
