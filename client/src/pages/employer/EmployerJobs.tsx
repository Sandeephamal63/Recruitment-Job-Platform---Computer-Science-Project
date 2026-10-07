import { useCallback, useEffect, useState } from 'react'
import { Button, Stack } from '@mui/material'
import { AddRounded } from '@mui/icons-material'
import { Link as RouterLink } from 'react-router-dom'
import { getErrorMessage } from '@/api/errors'
import * as applicationsApi from '@/api/applications'
import * as jobsApi from '@/api/jobs'
import PageLayout from '@/components/portal/PageLayout'
import EmployerJobsList from '@/features/employer/EmployerJobsList'
import type { Job } from '@/types/jobs'

/**
 * `/dashboard/jobs` — the employer's own postings.
 *
 * This route used to render the overview page, so the nav item labelled "My Jobs"
 * opened a screen of aggregate counters with no way to reach a posting. The
 * list itself already existed in `features/employer/EmployerJobsList` but nothing
 * rendered it; this is the container that fetches its data.
 */
export default function EmployerJobs() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [counts, setCounts] = useState<Record<string, number>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)

  const load = useCallback(async (signal?: { cancelled: boolean }) => {
    setLoading(true)
    setError(null)
    try {
      const [jobList, applicationCounts] = await Promise.all([
        jobsApi.listMyJobs(),
        applicationsApi.listApplicationCounts(),
      ])
      if (signal?.cancelled) return
      setJobs(jobList)
      setCounts(Object.fromEntries(applicationCounts.map((c) => [c.jobId, c.count])))
    } catch (err) {
      if (signal?.cancelled) return
      setError(getErrorMessage(err))
    } finally {
      if (!signal?.cancelled) setLoading(false)
    }
  }, [])

  useEffect(() => {
    const signal = { cancelled: false }
    load(signal)
    return () => {
      signal.cancelled = true
    }
  }, [attempt, load])

  const handleClose = useCallback(
    async (job: Job) => {
      try {
        await jobsApi.updateJob(job.id, { status: 'closed' })
        setJobs((current) =>
          current.map((j) => (j.id === job.id ? { ...j, status: 'closed' } : j)),
        )
      } catch (err) {
        setError(getErrorMessage(err))
      }
    },
    [],
  )

  return (
    <PageLayout title="My jobs" subtitle="Every role you have posted, open or closed.">
      <Stack spacing={2.5} alignItems="stretch">
        <Button
          component={RouterLink}
          to="/employer/jobs/new"
          variant="contained"
          startIcon={<AddRounded />}
          sx={{ alignSelf: { xs: 'stretch', sm: 'flex-end' }, width: { xs: '100%', sm: 'auto' } }}
        >
          Post a job
        </Button>
        <EmployerJobsList
          jobs={jobs}
          counts={counts}
          loading={loading}
          error={error}
          onRetry={() => setAttempt((n) => n + 1)}
          onClose={handleClose}
        />
      </Stack>
    </PageLayout>
  )
}
