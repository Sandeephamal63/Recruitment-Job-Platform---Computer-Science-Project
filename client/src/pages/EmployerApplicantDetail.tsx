import { DownloadRounded, MailOutlined, PersonOutlineOutlined } from '@mui/icons-material'
import { Alert, Box, Button, Card, Chip, CircularProgress, Divider, Stack, Typography } from '@mui/material'
import PageLayout from '@/components/portal/PageLayout'
import AvatarImage from '@/components/shared/AvatarImage'
import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import * as applicationsApi from '@/api/applications'
import { getErrorMessage } from '@/api/errors'
import { useToast } from '@/hooks/useToast'
import MatchReport from '@/features/matching/MatchReport'
import type { Application, ApplicationStatus } from '@/types/application'
import { layout } from '@/theme'

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

interface Transition {
  to: ApplicationStatus
  label: string
}

const NEXT_TRANSITIONS: Partial<Record<ApplicationStatus, Transition[]>> = {
  submitted: [
    { to: 'under_review', label: 'Move to under review' },
    { to: 'shortlisted', label: 'Shortlist' },
    { to: 'rejected', label: 'Reject' },
  ],
  under_review: [
    { to: 'shortlisted', label: 'Shortlist' },
    { to: 'rejected', label: 'Reject' },
  ],
  shortlisted: [{ to: 'rejected', label: 'Reject' }],
  rejected: [],
}

export default function EmployerApplicantDetail() {
  const toast = useToast()
  const { jobId, applicationId } = useParams<{ jobId: string; applicationId: string }>()
  const [application, setApplication] = useState<Application | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [transitioningTo, setTransitioningTo] = useState<ApplicationStatus | null>(null)
  const [downloading, setDownloading] = useState(false)

  const load = useCallback(async () => {
    if (!applicationId) return
    setLoading(true)
    setError(null)
    try {
      setApplication(await applicationsApi.getApplication(applicationId))
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [applicationId])

  useEffect(() => {
    load()
  }, [load])

  async function handleTransition(to: ApplicationStatus) {
    if (!applicationId) return
    setActionError(null)
    setTransitioningTo(to)
    try {
      await applicationsApi.updateApplicationStatus(applicationId, to)
      const label = to === 'under_review' ? 'Under Review' : to === 'shortlisted' ? 'Shortlisted' : 'Rejected'
      toast.success(`Status updated to ${label}.`)
      await load()
    } catch (err) {
      setActionError(getErrorMessage(err))
    } finally {
      setTransitioningTo(null)
    }
  }

  async function handleDownload() {
    if (!applicationId) return
    setActionError(null)
    setDownloading(true)
    try {
      const blob = await applicationsApi.downloadCv(applicationId)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = application?.cvFileName ?? 'cv'
      link.click()
      URL.revokeObjectURL(url)
      toast.info('CV download started.')
    } catch (err) {
      setActionError(getErrorMessage(err))
    } finally {
      setDownloading(false)
    }
  }

  const candidate = application?.candidate

  return (
    <PageLayout
      title={candidate?.name ?? 'Candidate'}
      subtitle={`Applied ${formatDate(application?.submittedAt ?? '')} for ${application?.job.title}`}
      back={{ to: `/employer/jobs/${jobId}/applicants`, label: 'Back to applicants' }}
      pb={0}
    >
      {loading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress />
        </Box>
      )}

      {!loading && (error || !application) && (
        <Alert severity="error" action={<Button color="inherit" size="small" onClick={load}>Retry</Button>}>
          {error ?? 'This application could not be loaded.'}
        </Alert>
      )}

      {!loading && !error && application && (
        <>
          {actionError && (
            <Alert severity="error" onClose={() => setActionError(null)} sx={{ mb: 3 }}>
              {actionError}
            </Alert>
          )}

          <Card variant="outlined" sx={{ p: layout.cardPadding }}>
            <Stack spacing={2}>
              <Stack direction="row" spacing={1} alignItems="center">
                <PersonOutlineOutlined color="action" />
                <Typography variant="h6">Candidate profile</Typography>
              </Stack>
              <Stack direction="row" spacing={2} alignItems="center">
                <AvatarImage
                  applicationId={application.id}
                  name={candidate?.name ?? 'Applicant'}
                  size={56}
                  alt=""
                />
                <Stack spacing={0.25} sx={{ minWidth: 0 }}>
                  <Typography variant="subtitle1">{candidate?.name}</Typography>
                  {candidate?.headline && (
                    <Typography variant="body2" color="text.secondary">
                      {candidate.headline}
                    </Typography>
                  )}
                  {candidate?.email && (
                    <Typography variant="body2" sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.75 }}>
                      <MailOutlined fontSize="small" color="action" />
                      {candidate.email}
                    </Typography>
                  )}
                </Stack>
              </Stack>
              {candidate && (candidate.skills ?? []).length > 0 && (
                <>
                  <Divider />
                  <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', rowGap: 1 }}>
                    {candidate.skills?.map((skill) => (
                      <Chip key={skill} label={skill} size="small" variant="outlined" />
                    ))}
                  </Stack>
                </>
              )}
              <Button
                startIcon={downloading ? <CircularProgress size={14} color="inherit" /> : <DownloadRounded />}
                onClick={handleDownload}
                disabled={downloading}
                variant="outlined"
                sx={{ alignSelf: 'flex-start' }}
              >
                Download CV{application.cvFileName ? ` (${application.cvFileName})` : ''}
              </Button>
            </Stack>
          </Card>

          <Card variant="outlined" sx={{ p: layout.cardPadding, mt: 3 }}>
            <Typography variant="h6" gutterBottom>
              Match analysis
            </Typography>
            <MatchReport matchResult={application.match} />
          </Card>

          <Card variant="outlined" sx={{ p: layout.cardPadding, mt: 3 }}>
            <Typography variant="h6" gutterBottom>
              Update status
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Move the candidate forward in your review funnel. Rejected applications can&apos;t move again.
            </Typography>
            <Stack direction="row" spacing={1.5} sx={{ flexWrap: 'wrap', rowGap: 1 }}>
              {(NEXT_TRANSITIONS[application.status] ?? []).map((transition) => (
                <Button
                  key={transition.to}
                  variant="outlined"
                  color={transition.to === 'rejected' ? 'warning' : transition.to === 'shortlisted' ? 'success' : 'info'}
                  startIcon={transitioningTo === transition.to ? <CircularProgress size={14} color="inherit" /> : null}
                  disabled={transitioningTo !== null}
                  onClick={() => handleTransition(transition.to)}
                >
                  {transition.label}
                </Button>
              ))}
              {application.status === 'rejected' && (
                <Typography variant="body2" color="text.secondary">
                  This application is rejected and can&apos;t be moved further.
                </Typography>
              )}
            </Stack>
          </Card>
        </>
      )}
    </PageLayout>
  )
}