import {
  ArrowBackRounded,
  CheckCircleOutlineRounded,
  EventOutlined,
  LocationOnOutlined,
  LockOutlined,
  ScheduleOutlined,
} from '@mui/icons-material'
import {
  Alert,
  Box,
  Button,
  Card,
  Chip,
  CircularProgress,
  Divider,
  Stack,
  Typography,
} from '@mui/material'
import { useEffect, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { getErrorMessage } from '@/api/errors'
import * as applicationsApi from '@/api/applications'
import { getJob } from '@/api/jobs'
import * as matchingApi from '@/api/matching'
import { useAuth } from '@/auth/AuthContext'
import ApplyForm from '@/features/candidate/ApplyForm'
import MatchReport from '@/features/matching/MatchReport'
import type { Application } from '@/types/application'
import type { Job } from '@/types/jobs'
import type { MatchResult } from '@/types/matching'
import CompanyInfoCard from '@/components/shared/CompanyInfoCard'
import Section from '@/components/public/Section'
import { deadlineView } from '@/utils/dates'

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

export default function JobDetail() {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const { user, loading: authLoading } = useAuth()
  const [job, setJob] = useState<Job | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [existing, setExisting] = useState<Application | null>(null)
  const [applied, setApplied] = useState<Application | null>(null)
  const [existingLoading, setExistingLoading] = useState(false)
  const [match, setMatch] = useState<MatchResult | null>(null)
  const [matchLoading, setMatchLoading] = useState(false)
  const deadline = deadlineView(job?.deadline)
  const [matchError, setMatchError] = useState<string | null>(null)
  const [matchReload, setMatchReload] = useState(0)

  useEffect(() => {
    if (!jobId) return
    const id = jobId
    let active = true
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const fetched = await getJob(id)
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

  useEffect(() => {
    let active = true
    if (!jobId || !user || user.role !== 'candidate') {
      setExisting(null)
      return
    }
    setExistingLoading(true)
    applicationsApi
      .listMyApplications()
      .then((apps) => {
        if (active) setExisting(apps.find((application) => application.jobId === jobId) ?? null)
      })
      .catch(() => {})
      .finally(() => {
        if (active) setExistingLoading(false)
      })
    return () => {
      active = false
    }
  }, [jobId, user])

  const alreadyApplied = existing ?? applied

  useEffect(() => {
    let active = true
    if (!alreadyApplied) {
      setMatch(null)
      return
    }
    setMatchLoading(true)
    setMatchError(null)
    matchingApi
      .getMatchResult(alreadyApplied.id)
      .then((result) => {
        if (active) setMatch(result)
      })
      .catch((err) => {
        if (active) setMatchError(getErrorMessage(err))
      })
      .finally(() => {
        if (active) setMatchLoading(false)
      })
    return () => {
      active = false
    }
  }, [alreadyApplied, matchReload])

  return (
    <Section spacing="tight">
      <Stack spacing={3}>
        <Button
          startIcon={<ArrowBackRounded />}
          onClick={() => navigate('/jobs')}
          sx={{ alignSelf: 'flex-start', color: 'text.secondary' }}
        >
          Back to jobs
        </Button>
        {loading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
            <CircularProgress />
          </Box>
        )}
        {!loading && (error || !job) && (
          <Stack spacing={2} alignItems="flex-start">
            <Typography variant="h4" component="h1">
              This role is not available
            </Typography>
            <Alert severity="error">{error ?? 'This job could not be loaded.'}</Alert>
          </Stack>
        )}
        {!loading && !error && job && (
          <>
            <Card variant="outlined" sx={{ p: 4 }}>
              <Stack direction="row" alignItems="flex-start" spacing={1} sx={{ flexWrap: 'wrap', rowGap: 1 }}>
                <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                  <Typography variant="h4" component="h1" gutterBottom>
                    {job.title}
                  </Typography>
                  <Stack direction="row" spacing={2} sx={{ color: 'text.secondary', flexWrap: 'wrap' }}>
                    <Typography variant="body2" sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5 }}>
                      <LocationOnOutlined fontSize="small" />
                      {job.location}
                    </Typography>
                    <Typography variant="body2" sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5 }}>
                      <ScheduleOutlined fontSize="small" />
                      {job.employmentType.replace('-', ' ')}
                    </Typography>
                    <Typography variant="body2">Posted {formatDate(job.createdAt)}</Typography>
                    {deadline && (
                      <Typography
                        variant="body2"
                        sx={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 0.5,
                          fontWeight: 500,
                          color: deadline.urgent ? 'warning.main' : 'text.secondary',
                        }}
                      >
                        <EventOutlined fontSize="small" />
                        {deadline.label}
                      </Typography>
                    )}
                  </Stack>
                </Box>
              </Stack>
              <Typography component="div" variant="body1" sx={{ mt: 2, whiteSpace: 'pre-line' }}>
                {job.description}
              </Typography>
              {job.requiredSkills.length > 0 && (
                <>
                  <Divider sx={{ my: 2.5 }} />
                  <Typography variant="subtitle2" component="h2" sx={{ mb: 1 }}>
                    Required skills
                  </Typography>
                  <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', rowGap: 1 }}>
                    {job.requiredSkills.map((skill) => (
                      <Chip key={skill} label={skill} variant="outlined" />
                    ))}
                  </Stack>
                </>
              )}
            </Card>
            {job.employer && <CompanyInfoCard employer={job.employer} sx={{ p: 4 }} />}
            <Card variant="outlined" sx={{ p: 4 }}>
              {authLoading || existingLoading ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                  <CircularProgress size={28} />
                </Box>
              ) : !user ? (
                <Stack spacing={2} alignItems="flex-start">
                  <Typography variant="h6">Interested in this role?</Typography>
                  <Typography variant="body2" color="text.secondary">
                    Log in as a candidate to apply with your CV.
                  </Typography>
                  <Button
                    variant="contained"
                    startIcon={<LockOutlined />}
                    onClick={() => navigate('/login', { state: { from: location.pathname } })}
                  >
                    Log in to apply
                  </Button>
                </Stack>
              ) : user.role !== 'candidate' ? (
                <Typography variant="body2" color="text.secondary">
                  You are signed in as an employer, so you can&apos;t apply for this role.
                </Typography>
              ) : alreadyApplied ? (
                <Stack spacing={3}>
                  <Stack spacing={1.5}>
                    <Stack direction="row" spacing={1} alignItems="center">
                      <CheckCircleOutlineRounded color="success" />
                      <Typography variant="h6">Application submitted</Typography>
                    </Stack>
                    <Typography variant="body2" color="text.secondary">
                      You applied on {formatDate(alreadyApplied.submittedAt)}. Track its status from your dashboard.
                    </Typography>
                    <Stack direction="row" spacing={1.5} sx={{ flexWrap: 'wrap', rowGap: 1 }}>
                      <Button
                        variant="contained"
                        onClick={() => navigate(`/candidate/applications/${alreadyApplied.id}`)}
                        sx={{ alignSelf: 'flex-start' }}
                      >
                        View this application
                      </Button>
                      <Button
                        variant="outlined"
                        onClick={() => navigate('/candidate/applications')}
                        sx={{ alignSelf: 'flex-start' }}
                      >
                        All my applications
                      </Button>
                    </Stack>
                  </Stack>
                  <Divider />
                  <MatchReport
                    matchResult={match}
                    loading={matchLoading}
                    error={matchError}
                    onRetry={() => setMatchReload((count) => count + 1)}
                  />
                </Stack>
              ) : (
                <ApplyForm jobId={job.id} jobTitle={job.title} onApplied={setApplied} />
              )}
            </Card>
          </>
        )}
      </Stack>
      </Section>
  )
}