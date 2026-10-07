import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Stack,
  Typography,
} from '@mui/material'
import Grid from '@mui/material/Grid2'
import {
  AddRounded,
  AssignmentRounded,
  PeopleRounded,
  TrendingUpRounded,
  WorkOutlineRounded,
} from '@mui/icons-material'
import { Link as RouterLink } from 'react-router-dom'
import { getErrorMessage } from '@/api/errors'
import * as jobsApi from '@/api/jobs'
import type { JobFunnelEntry } from '@/api/jobs'
import { useAuth } from '@/auth/AuthContext'
import PageLayout from '@/components/portal/PageLayout'
import { brand, neutral } from '@/theme'

/** The five funnel stages, in pipeline order. Keys match the API's camelCase. */
const STAGES = [
  { key: 'submitted', label: 'Submitted' },
  { key: 'underReview', label: 'Under review' },
  { key: 'shortlisted', label: 'Shortlisted' },
  { key: 'rejected', label: 'Rejected' },
  { key: 'withdrawn', label: 'Withdrawn' },
] as const satisfies ReadonlyArray<{ key: keyof JobFunnelEntry['stages']; label: string }>

interface Stats {
  openJobs: number
  closedJobs: number
  totalApplicants: number
  shortlisted: number
  averageScore: number | null
}

const EMPTY_STATS: Stats = {
  openJobs: 0,
  closedJobs: 0,
  totalApplicants: 0,
  shortlisted: 0,
  averageScore: null,
}

function StatCard({
  title,
  value,
  icon,
}: {
  title: string
  value: string
  icon: React.ReactNode
}) {
  return (
    <Card variant="outlined" sx={{ height: '100%', borderRadius: 3 }}>
      <CardContent>
        <Stack direction="row" spacing={1.5} alignItems="center">
          <Box sx={{ color: brand.primary, display: 'flex', '& svg': { fontSize: 22 } }}>{icon}</Box>
          <Typography variant="body2" color="text.secondary">
            {title}
          </Typography>
        </Stack>
        <Typography variant="h3" component="p" sx={{ mt: 1.25, color: 'text.primary' }}>
          {value}
        </Typography>
      </CardContent>
    </Card>
  )
}

function SkeletonRows({ rows }: { rows: number }) {
  return (
    <Stack spacing={2} aria-hidden>
      {Array.from({ length: rows }, (_, i) => (
        <Box key={i} sx={{ height: 56, borderRadius: 2, bgcolor: neutral[100] }} />
      ))}
    </Stack>
  )
}

/**
 * Employer overview: headline counters plus the per-job applicant funnel.
 *
 * Owns `/dashboard` only. The other employer routes are separate pages; this one
 * used to be registered for `/dashboard/jobs`, `/dashboard/analytics` and
 * `/dashboard/settings` as well, so all four URLs rendered the same screen.
 */
export default function EmployerOverview() {
  const { user } = useAuth()
  const [stats, setStats] = useState<Stats>(EMPTY_STATS)
  const [funnel, setFunnel] = useState<JobFunnelEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let active = true
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const [overview, funnelData] = await Promise.all([
          jobsApi.getEmployerOverview(),
          jobsApi.getEmployerFunnel(),
        ])
        if (!active) return
        setStats({ ...EMPTY_STATS, ...overview })
        setFunnel(funnelData)
      } catch (err) {
        if (!active) return
        setError(getErrorMessage(err))
      } finally {
        if (active) setLoading(false)
      }
    }
    load()
    return () => {
      active = false
    }
  }, [attempt])

  const retry = useCallback(() => setAttempt((n) => n + 1), [])

  const totalsByStage = useMemo(() => {
    const totals: Record<string, number> = {}
    for (const job of funnel) {
      for (const stage of STAGES) {
        totals[stage.key] = (totals[stage.key] ?? 0) + (job.stages[stage.key] ?? 0)
      }
    }
    return totals
  }, [funnel])

  const denominator = stats.totalApplicants || 1

  return (
    <PageLayout
      title={`Welcome back, ${user?.name || 'there'}`}
      subtitle="How your roles and applicants are tracking."
    >
      <Stack spacing={3}>
        {error && (
          <Alert severity="error" action={<Button color="inherit" size="small" onClick={retry}>Retry</Button>}>
            {error}
          </Alert>
        )}

        <Grid container spacing={2.5}>
          <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
            <StatCard title="Open jobs" value={String(stats.openJobs)} icon={<WorkOutlineRounded />} />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
            <StatCard title="Total applicants" value={String(stats.totalApplicants)} icon={<PeopleRounded />} />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
            <StatCard title="Shortlisted" value={String(stats.shortlisted)} icon={<TrendingUpRounded />} />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
            <StatCard
              title="Average match score"
              value={stats.averageScore === null ? '—' : `${Math.round(stats.averageScore)}%`}
              icon={<AssignmentRounded />}
            />
          </Grid>
        </Grid>

        <Grid container spacing={2.5}>
          <Grid size={{ xs: 12, lg: 8 }}>
            <Card variant="outlined" sx={{ height: '100%', borderRadius: 3 }}>
              <CardContent>
                <Stack
                  direction="row"
                  spacing={2}
                  justifyContent="space-between"
                  alignItems="center"
                  sx={{ mb: 2.5 }}
                >
                  <Typography variant="h3" component="h2" sx={{ fontSize: 18, color: 'text.primary' }}>
                    Applicant pipeline
                  </Typography>
                  <Button component={RouterLink} to="/dashboard/applicants" size="small" variant="outlined">
                    View all
                  </Button>
                </Stack>

                {loading ? (
                  <SkeletonRows rows={3} />
                ) : funnel.length === 0 ? (
                  <Stack spacing={1.5} alignItems="flex-start" sx={{ py: 3 }}>
                    <Typography variant="body2" color="text.secondary">
                      No jobs posted yet. Post a role and applicants will appear here, scored
                      against the job description.
                    </Typography>
                    <Button
                      component={RouterLink}
                      to="/employer/jobs/new"
                      size="small"
                      variant="contained"
                      startIcon={<AddRounded />}
                    >
                      Post a job
                    </Button>
                  </Stack>
                ) : (
                  <Stack spacing={2}>
                    {funnel.slice(0, 5).map((job) => (
                      <Box key={job.jobId} sx={{ pb: 2, borderBottom: `1px solid ${neutral[200]}` }}>
                        <Typography variant="subtitle1" sx={{ fontWeight: 700, color: 'text.primary' }}>
                          {job.title}
                        </Typography>
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                          {job.stages.total} applicant{job.stages.total === 1 ? '' : 's'}
                        </Typography>
                        <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', rowGap: 1 }}>
                          {STAGES.map((stage) => (
                            <Chip
                              key={stage.key}
                              size="small"
                              variant="outlined"
                              label={`${stage.label}: ${job.stages[stage.key] ?? 0}`}
                            />
                          ))}
                        </Stack>
                      </Box>
                    ))}
                  </Stack>
                )}
              </CardContent>
</Card>
          </Grid>
          <Grid size={{ xs: 12, lg: 4 }}>
            <Card variant="outlined" sx={{ height: '100%', borderRadius: 3 }}>
              <CardContent>
                <Typography variant="h3" component="h2" sx={{ fontSize: 18, color: 'text.primary', mb: 2.5 }}>
                  Funnel summary
                </Typography>
                {loading ? (
                  <SkeletonRows rows={5} />
                ) : (
                  <Stack spacing={1.5}>
                    {STAGES.map((stage) => {
                      const count = totalsByStage[stage.key] ?? 0
                      const percent = Math.round((count / denominator) * 100)
                      return (
                        <Box key={stage.key}>
                          <Stack direction="row" justifyContent="space-between" sx={{ mb: 0.5 }}>
                            <Typography variant="body2" sx={{ color: 'text.primary' }}>
                              {stage.label}
                            </Typography>
                            <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                              {count} ({percent}%)
                            </Typography>
                          </Stack>
                          <Box
                            role="presentation"
                            sx={{ height: 6, borderRadius: 3, bgcolor: neutral[200], overflow: 'hidden' }}
                          >
                            <Box
                              sx={{
                                width: `${percent}%`,
                                height: '100%',
                                borderRadius: 3,
                                bgcolor: brand.primary,
                                transition: 'width 0.4s ease',
                              }}
                            />
                          </Box>
                        </Box>
                      )
                    })}
                  </Stack>
                )}
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </Stack>
    </PageLayout>
  )
}
