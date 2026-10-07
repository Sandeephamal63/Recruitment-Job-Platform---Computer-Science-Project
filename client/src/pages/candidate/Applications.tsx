import { useEffect, useState } from 'react'
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
  WorkOutlineRounded,
  ArrowForwardRounded,
  CheckCircleRounded,
  CancelRounded,
  HourglassTopRounded,
  SendRounded,
  RemoveCircleOutlineRounded,
  NotificationsActiveRounded,
} from '@mui/icons-material'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/auth/AuthContext'
import * as profileApi from '@/api/profile'
import * as applicationsApi from '@/api/applications'
import { getErrorMessage } from '@/api/errors'
import { Application } from '@/types/application'
import { User } from '@/types/profile'
import MatchReport from '@/features/matching/MatchReport'
import CompanyMark from '@/components/shared/CompanyMark'
import PageLayout from '@/components/portal/PageLayout'

export default function CandidateApplications() {
  const navigate = useNavigate()
  const { user, isAuthenticated } = useAuth()
  const [_profile, setProfile] = useState<User | null>(null)
  const [applications, setApplications] = useState<Application[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    async function fetchData() {
      setLoading(true)
      setLoadError(null)
      try {
        const [profileData, appsData] = await Promise.all([
          profileApi.getProfile(),
          applicationsApi.listMyApplications(),
        ])
        if (!active) return
        setProfile(profileData)
        setApplications(appsData)
      } catch (error) {
        if (!active) return
        setLoadError(getErrorMessage(error))
      } finally {
        if (active) setLoading(false)
      }
    }
    fetchData()
    return () => { active = false }
  }, [])

  if (!isAuthenticated || user?.role !== 'candidate') {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', bgcolor: 'background.default' }}>
        <Typography variant="h5" color="text.secondary">Please sign in as a candidate</Typography>
      </Box>
    )
  }

  type StatusConfig = {
    color: 'primary' | 'secondary' | 'success' | 'warning' | 'error' | 'info'
    label: string
    icon: React.ReactElement
    borderColor: string
    bgColor: string
    employerUpdated: boolean
    description: string
  }

  const getStatusConfig = (status: string): StatusConfig => {
    const configs: Record<string, StatusConfig> = {
      submitted: {
        color: 'info',
        label: 'Submitted',
        icon: <SendRounded fontSize="small" />,
        borderColor: 'info.main',
        bgColor: 'rgba(2, 136, 209, 0.04)',
        employerUpdated: false,
        description: 'Your application has been submitted and is awaiting review.',
      },
      under_review: {
        color: 'warning',
        label: 'Under Review',
        icon: <HourglassTopRounded fontSize="small" />,
        borderColor: 'warning.main',
        bgColor: 'rgba(237, 108, 2, 0.04)',
        employerUpdated: true,
        description: 'The employer is currently reviewing your application.',
      },
      shortlisted: {
        color: 'success',
        label: 'Shortlisted! 🎉',
        icon: <CheckCircleRounded fontSize="small" />,
        borderColor: 'success.main',
        bgColor: 'rgba(46, 125, 50, 0.06)',
        employerUpdated: true,
        description: 'Congratulations! You have been shortlisted by the employer.',
      },
      rejected: {
        color: 'error',
        label: 'Not Selected',
        icon: <CancelRounded fontSize="small" />,
        borderColor: 'error.main',
        bgColor: 'rgba(211, 47, 47, 0.04)',
        employerUpdated: true,
        description: 'The employer has decided not to move forward with your application.',
      },
      withdrawn: {
        color: 'secondary',
        label: 'Withdrawn',
        icon: <RemoveCircleOutlineRounded fontSize="small" />,
        borderColor: 'text.disabled',
        bgColor: 'transparent',
        employerUpdated: false,
        description: 'You have withdrawn this application.',
      },
    }
    return configs[status] || {
      color: 'secondary',
      label: status,
      icon: <SendRounded fontSize="small" />,
      borderColor: 'divider',
      bgColor: 'transparent',
      employerUpdated: false,
      description: '',
    }
  }

  if (loading) {
    return (
      <PageLayout title="Applications" subtitle="Your job applications and their status.">
        <Stack spacing={3} sx={{ maxWidth: 800, mx: 'auto' }}>
          <Grid container spacing={3}>
            {[1, 2, 3].map((i) => (
              <Grid size={{ xs: 12, sm: 6 }} key={i}>
                <Box component="span" sx={{ display: 'block', height: 180, borderRadius: 2, bgcolor: 'action.hover', animation: 'pulse 1.5s infinite' }} />
              </Grid>
            ))}
          </Grid>
        </Stack>
      </PageLayout>
    )
  }

  return (
    <PageLayout title="Applications" subtitle="Track your job applications and their status.">
      {loadError && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {loadError}
          <Button size="small" color="inherit" onClick={() => window.location.reload()} sx={{ ml: 2 }}>Retry</Button>
        </Alert>
      )}

      {applications.length === 0 ? (
        <Card variant="outlined" sx={{ p: 4, textAlign: 'center' }}>
          <WorkOutlineRounded sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
          <Typography variant="h6" color="text.primary" sx={{ mb: 1 }}>No applications yet</Typography>
          <Typography variant="body1" color="text.secondary" sx={{ mb: 3, maxWidth: 400, mx: 'auto' }}>
            Start applying to jobs to see them here. Your applications will appear with their status and match scores.
          </Typography>
          <Button variant="contained" size="large" startIcon={<ArrowForwardRounded />} onClick={() => navigate('/jobs')}>
            Browse Jobs
          </Button>
        </Card>
      ) : (
        <>
          <Stack direction="row" spacing={2} justifyContent="space-between" alignItems="center" sx={{ mb: 3 }}>
            <Typography variant="h6" fontWeight={700}>Your Applications ({applications.length})</Typography>
          </Stack>
          <Stack spacing={2}>
            {applications.map((app) => {
              const sc = getStatusConfig(app.status)
              return (
                <Card
                  key={app.id}
                  variant="outlined"
                  sx={{
                    borderLeftWidth: 4,
                    borderLeftColor: sc.borderColor,
                    bgcolor: sc.bgColor,
                    transition: 'box-shadow 0.2s',
                    '&:hover': { boxShadow: 3 },
                  }}
                >
                  <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                    <Stack direction="row" spacing={2} justifyContent="space-between" alignItems="flex-start" sx={{ flexWrap: 'wrap', gap: 1 }}>
                      <Box sx={{ flex: 1, minWidth: 220 }}>
                        <Stack direction="row" spacing={1} alignItems="center" sx={{ flexWrap: 'wrap', mb: 0.5 }}>
                          <Typography variant="subtitle1" fontWeight={700}>
                            {app.job?.title || 'Job'}
                          </Typography>
                          {app.match && <MatchReport matchResult={app.match} variant="compact" />}
                        </Stack>
                        <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.5, minWidth: 0 }}>
                          <CompanyMark
                            name={app.employer?.companyName || app.job?.title || 'Company'}
                            logoUrl={app.employer?.companyLogoUrl}
                            size={24}
                          />
                          <Typography variant="body2" color="text.secondary" noWrap>
                            {app.employer?.companyName || 'Company no longer available'}
                          </Typography>
                        </Stack>
                        <Typography variant="caption" color="text.secondary">
                          Applied {new Date(app.submittedAt).toLocaleDateString()}
                        </Typography>
                      </Box>

                      <Stack spacing={1} alignItems="flex-end" sx={{ minWidth: 160 }}>
                        <Chip
                          icon={sc.icon}
                          label={sc.label}
                          size="small"
                          color={sc.color}
                          variant="filled"
                          sx={{ fontWeight: 600 }}
                        />
                        {sc.employerUpdated && (
                          <Chip
                            icon={<NotificationsActiveRounded sx={{ fontSize: '0.75rem !important' }} />}
                            label="Updated by employer"
                            size="small"
                            variant="outlined"
                            color="default"
                            sx={{ fontSize: '0.65rem', height: 20 }}
                          />
                        )}
                        {app.match && (
                          <Chip label={`${app.match.matchedSkills?.length || 0} matched skills`} size="small" variant="outlined" color="primary" />
                        )}
                        <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', rowGap: 1 }}>
                          <Button size="small" variant="contained" onClick={() => navigate(`/candidate/applications/${app.id}`)}>
                            View details
                          </Button>
                          <Button size="small" variant="outlined" onClick={() => navigate(`/jobs/${app.jobId}`)}>
                            View Job
                          </Button>
                        </Stack>
                      </Stack>
                    </Stack>

                    {sc.employerUpdated && (
                      <Box
                        sx={{
                          mt: 1.5,
                          pt: 1.5,
                          borderTop: '1px solid',
                          borderColor: 'divider',
                        }}
                      >
                        <Typography variant="caption" color="text.secondary" sx={{ fontStyle: 'italic' }}>
                          {sc.description}
                        </Typography>
                        {app.status === 'rejected' && app.rejectionReason && (
                          <Alert severity="error" sx={{ mt: 1, py: 0.5, fontSize: '0.8rem' }}>
                            <strong>Employer feedback:</strong> {app.rejectionReason}
                          </Alert>
                        )}
                      </Box>
                    )}
                  </CardContent>
                </Card>
              )
            })}
          </Stack>
        </>
      )}
    </PageLayout>
  )
}