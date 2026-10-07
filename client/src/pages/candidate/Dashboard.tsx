import { useEffect, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Stack,
  Typography,
} from '@mui/material'
import Grid from '@mui/material/Grid2'
import {
  PersonRounded,
  SearchRounded,
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
import { getMyRecommendations } from '@/api/matching'
import { getErrorMessage } from '@/api/errors'
import { Application } from '@/types/application'
import { User } from '@/types/profile'
import { JobRecommendation } from '@/types/matching'
import MatchReport from '@/features/matching/MatchReport'
import RecommendationCard from '@/features/candidate/RecommendationCard'
import CompanyMark from '@/components/shared/CompanyMark'
import PageLayout from '@/components/portal/PageLayout'

const RECOMMENDATION_LIMIT = 4

export default function CandidateDashboard() {
  const navigate = useNavigate()
  const { user, isAuthenticated } = useAuth()
  const [profile, setProfile] = useState<User | null>(null)
  const [applications, setApplications] = useState<Application[]>([])
  const [recommendations, setRecommendations] = useState<JobRecommendation[]>([])
  const [recommendationsLoading, setRecommendationsLoading] = useState(true)
  const [recommendationsError, setRecommendationsError] = useState<string | null>(null)
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

  // Fetched separately from the profile and applications: a ranking is a slow,
  // optional enhancement, and failing it must not blank the whole dashboard.
  useEffect(() => {
    let active = true
    async function fetchRecommendations() {
      setRecommendationsLoading(true)
      setRecommendationsError(null)
      try {
        const data = await getMyRecommendations(RECOMMENDATION_LIMIT)
        if (!active) return
        setRecommendations(data.recommendations)
      } catch (error) {
        if (!active) return
        setRecommendationsError(getErrorMessage(error))
      } finally {
        if (active) setRecommendationsLoading(false)
      }
    }
    fetchRecommendations()
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
      <PageLayout>
        <Stack spacing={3} sx={{ maxWidth: 800, mx: 'auto' }}>
          <Stack direction="row" spacing={2} alignItems="center" justifyContent="space-between">
            <Box component="span" sx={{ width: 150, height: 32, borderRadius: 2, bgcolor: 'action.hover', animation: 'pulse 1.5s infinite' }} />
            <Box component="span" sx={{ width: 100, height: 32, borderRadius: 2, bgcolor: 'action.hover', animation: 'pulse 1.5s infinite' }} />
          </Stack>
          <Grid container spacing={3}>
            {[1, 2, 3, 4].map((i) => (
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
    <PageLayout
      title={`Welcome back, ${profile?.name || user?.name || 'there'}`}
      subtitle="Your applications and personalized recommendations."
    >
      {loadError && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {loadError}
          <Button size="small" color="inherit" onClick={() => window.location.reload()} sx={{ ml: 2 }}>
            Retry
          </Button>
        </Alert>
      )}

      <Grid container spacing={2} sx={{ mb: 4 }}>
        <Grid size={{ xs: 6, sm: 3 }}>
          <Card variant="outlined" sx={{ p: 2, height: '100%', textAlign: 'center' }}>
            <Typography variant="h4" fontWeight={700} color="primary.main">
              {applications.length}
            </Typography>
            <Typography variant="body2" color="text.secondary">Applications</Typography>
          </Card>
        </Grid>
        <Grid size={{ xs: 6, sm: 3 }}>
          <Card variant="outlined" sx={{ p: 2, height: '100%', textAlign: 'center' }}>
            <Typography variant="h4" fontWeight={700} color="success.main">
              {applications.filter(a => a.status === 'shortlisted').length}
            </Typography>
            <Typography variant="body2" color="text.secondary">Shortlisted</Typography>
          </Card>
        </Grid>
        <Grid size={{ xs: 6, sm: 3 }}>
          <Card variant="outlined" sx={{ p: 2, height: '100%', textAlign: 'center' }}>
            <Typography variant="h4" fontWeight={700} color="info.main">
              {recommendations.length}
            </Typography>
            <Typography variant="body2" color="text.secondary">Recommendations</Typography>
          </Card>
        </Grid>
        <Grid size={{ xs: 6, sm: 3 }}>
          <Card variant="outlined" sx={{ p: 2, height: '100%', textAlign: 'center' }}>
            <Typography variant="h4" fontWeight={700} color={profile?.hasProfileCv ? 'success.main' : 'warning.main'}>
              {profile?.hasProfileCv ? '✓' : '!'}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {profile?.hasProfileCv ? 'CV Ready' : 'CV Missing'}
            </Typography>
          </Card>
        </Grid>
      </Grid>

      <Stack direction="row" spacing={2} sx={{ mb: 4, flexWrap: 'wrap' }}>
        <Button
          variant="contained"
          size="large"
          startIcon={<SearchRounded />}
          onClick={() => navigate('/jobs')}
          sx={{ px: 4, width: { xs: '100%', sm: 'auto' }, minWidth: { sm: 180 } }}
        >
          Browse Jobs
        </Button>
        <Button
          variant="outlined"
          size="large"
          startIcon={<PersonRounded />}
          onClick={() => navigate('/candidate/profile')}
          sx={{ px: 4, width: { xs: '100%', sm: 'auto' }, minWidth: { sm: 180 } }}
        >
          Complete Profile
        </Button>
      </Stack>

      {applications.length > 0 && (
        <Stack spacing={3} sx={{ mb: 4 }}>
          <Stack
            direction={{ xs: 'column', sm: 'row' }}
            spacing={{ xs: 1, sm: 2 }}
            justifyContent="space-between"
            alignItems={{ xs: 'flex-start', sm: 'center' }}
            sx={{ rowGap: 1 }}
          >
            <Typography variant="h6" fontWeight={700}>Recent Applications</Typography>
            <Button
              size="small"
              variant="outlined"
              onClick={() => navigate('/candidate/applications')}
              sx={{ width: { xs: '100%', sm: 'auto' } }}
            >
              View All
            </Button>
          </Stack>
          <Stack spacing={2}>
            {applications.slice(0, 3).map((app) => {
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
                    <Stack
                      direction={{ xs: 'column', sm: 'row' }}
                      spacing={{ xs: 1.5, sm: 2 }}
                      justifyContent="space-between"
                      alignItems={{ xs: 'stretch', sm: 'flex-start' }}
                    >
                      <Box sx={{ flex: 1, minWidth: 0 }}>
                        <Stack direction="row" spacing={1} alignItems="center" sx={{ flexWrap: 'wrap', mb: 0.5 }}>
                          <Typography variant="subtitle1" fontWeight={700} noWrap>
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

                      <Stack
                        spacing={1}
                        alignItems={{ xs: 'flex-start', sm: 'flex-end' }}
                        sx={{ width: { xs: '100%', sm: 'auto' }, minWidth: { sm: 160 } }}
                      >
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
                        <Stack
                          direction={{ xs: 'column', sm: 'row' }}
                          spacing={{ xs: 0.75, sm: 1 }}
                          sx={{ width: { xs: '100%', sm: 'auto' }, rowGap: 1 }}
                        >
                          <Button
                            size="small"
                            variant="contained"
                            onClick={() => navigate(`/candidate/applications/${app.id}`)}
                            sx={{ width: { xs: '100%', sm: 'auto' } }}
                          >
                            View details
                          </Button>
                          <Button
                            size="small"
                            variant="outlined"
                            onClick={() => navigate(`/jobs/${app.jobId}`)}
                            sx={{ width: { xs: '100%', sm: 'auto' } }}
                          >
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
        </Stack>
      )}

      <Stack spacing={3} sx={{ mb: 4 }}>
          <Stack
            direction={{ xs: 'column', sm: 'row' }}
            spacing={{ xs: 1, sm: 2 }}
            justifyContent="space-between"
            alignItems={{ xs: 'flex-start', sm: 'center' }}
            sx={{ rowGap: 1 }}
          >
            <Typography variant="h6" fontWeight={700}>Recommended for You</Typography>
            <Typography variant="body2" color="text.secondary">
              Scored against your profile, highest fit first.
            </Typography>
          </Stack>

        {recommendationsLoading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress size={28} />
          </Box>
        ) : recommendationsError ? (
          <Alert
            severity="error"
            action={
              <Button color="inherit" size="small" onClick={() => window.location.reload()}>
                Retry
              </Button>
            }
          >
            Could not load your recommendations. {recommendationsError}
          </Alert>
        ) : recommendations.length === 0 ? (
          <Card variant="outlined" sx={{ p: 3, textAlign: 'center' }}>
            <Typography variant="body1" color="text.secondary">
              No recommendations yet.
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              Recommendations are scored from your CV and skills, so add them to your profile
              and they will appear here.
            </Typography>
            <Button
              variant="outlined"
              size="small"
              startIcon={<PersonRounded />}
              onClick={() => navigate('/candidate/profile')}
              sx={{ mt: 2 }}
            >
              Update Profile
            </Button>
          </Card>
        ) : (
          <Grid container spacing={3}>
            {recommendations.map((recommendation) => (
              <Grid size={{ xs: 12, sm: 6, lg: 3 }} key={recommendation.jobId}>
                <RecommendationCard
                  recommendation={recommendation}
                  onViewJob={(jobId) => navigate(`/jobs/${jobId}`)}
                />
              </Grid>
            ))}
          </Grid>
        )}
      </Stack>

      {applications.length === 0 && !recommendationsLoading && recommendations.length === 0 && (
        <Card variant="outlined" sx={{ p: { xs: 3, sm: 4 }, textAlign: 'center', mt: 4 }}>
          <SearchRounded sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
          <Typography variant="h6" color="text.primary" sx={{ mb: 1 }}>
            Start your job search
          </Typography>
          <Typography variant="body1" color="text.secondary" sx={{ mb: 3, maxWidth: 400, mx: 'auto' }}>
            Browse open positions, save jobs you like, and apply with your CV. We'll show personalized recommendations once you have a profile.
          </Typography>
          <Stack direction="row" spacing={2} justifyContent="center" sx={{ flexWrap: 'wrap' }}>
            <Button
              variant="contained"
              size="large"
              startIcon={<SearchRounded />}
              onClick={() => navigate('/jobs')}
              sx={{ width: { xs: '100%', sm: 'auto' } }}
            >
              Browse Jobs
            </Button>
            <Button
              variant="outlined"
              size="large"
              startIcon={<PersonRounded />}
              onClick={() => navigate('/candidate/profile')}
              sx={{ width: { xs: '100%', sm: 'auto' } }}
            >
              Complete Profile
            </Button>
          </Stack>
        </Card>
      )}
    </PageLayout>
  )
}