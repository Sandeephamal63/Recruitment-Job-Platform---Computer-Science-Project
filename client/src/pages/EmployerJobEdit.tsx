import { Alert, Box, Card, CircularProgress } from '@mui/material'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { DASHBOARD_PATH } from '@/auth/RequireAuth'
import PageLayout from '@/components/portal/PageLayout'
import { getErrorMessage } from '@/api/errors'
import * as jobsApi from '@/api/jobs'
import { layout } from '@/theme'
import JobForm from '@/features/employer/JobForm'
import type { Job } from '@/types/jobs'

export default function EmployerJobEdit() {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  const [job, setJob] = useState<Job | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!jobId) return
    const id = jobId
    let active = true
    async function load() {
      try {
        const fetched = await jobsApi.getJob(id)
        if (active) setJob(fetched)
      } catch (err) {
        if (active) setError(getErrorMessage(err))
      } finally {
        if (active) setLoading(false)
      }
    }
    load()
    return () => {
      active = false
    }
  }, [jobId])

  return (
    <PageLayout
      title="Edit job"
      back={{ to: DASHBOARD_PATH, label: 'Back to dashboard' }}
      pb={0}
    >
      {loading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress />
        </Box>
      )}
      {!loading && (error || !job) && (
        <Alert severity="error">{error ?? 'This job could not be loaded.'}</Alert>
      )}
      {!loading && !error && job && (
        <Card variant="outlined" sx={{ p: layout.cardPadding }}>
          <JobForm
            mode="edit"
            job={job}
            onSaved={() => navigate(DASHBOARD_PATH)}
            onCancel={() => navigate(DASHBOARD_PATH)}
          />
        </Card>
      )}
    </PageLayout>
  )
}
