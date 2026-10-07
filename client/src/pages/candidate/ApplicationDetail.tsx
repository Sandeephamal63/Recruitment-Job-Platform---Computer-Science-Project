import { useCallback, useEffect, useState } from 'react'
import { Alert, Box, Button, Card, Chip, CircularProgress, Divider, Stack, Typography } from '@mui/material'
import {
  BusinessOutlined,
  DownloadRounded,
  InsertDriveFileOutlined,
  LocationOnOutlined,
  ScheduleOutlined,
} from '@mui/icons-material'
import { useNavigate, useParams } from 'react-router-dom'
import * as applicationsApi from '@/api/applications'
import { getErrorMessage } from '@/api/errors'
import MatchReport from '@/features/matching/MatchReport'
import CompanyInfoCard from '@/components/shared/CompanyInfoCard'
import PageLayout from '@/components/portal/PageLayout'
import { useToast } from '@/hooks/useToast'
import { layout } from '@/theme'
import type { Application, ApplicationStatus } from '@/types/application'

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

const STATUS_VIEWS: Record<ApplicationStatus, { label: string; color: 'default' | 'info' | 'success' | 'warning' | 'error' }> = {
  submitted: { label: 'Submitted', color: 'default' },
  under_review: { label: 'Under review', color: 'info' },
  shortlisted: { label: 'Shortlisted', color: 'success' },
  rejected: { label: 'Not selected', color: 'error' },
  withdrawn: { label: 'Withdrawn', color: 'warning' },
}

/**
 * A candidate's own view of one application.
 *
 * The employer-facing twin of this page lives at `EmployerApplicantDetail`; the
 * two share the load/error/empty shape and the `MatchReport` renderer, but not
 * the content. An employer is looking at a person and deciding; a candidate is
 * looking at a decision that was made about them. So this side leads with the
 * status and the employer's feedback, and carries no review controls — those
 * are employer actions, and the only writes available to a candidate are
 * withdrawing and downloading their own CV.
 *
 * The company block is the reason this page exists as its own screen: the
 * applications list names the company in one line, and this is where a candidate
 * finds out who they applied to — what they do, how big they are — after the
 * fact rather than by going back to the job advert.
 */
export default function ApplicationDetail() {
  const { applicationId } = useParams<{ applicationId: string }>()
  const navigate = useNavigate()
  const toast = useToast()
  const [application, setApplication] = useState<Application | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [downloading, setDownloading] = useState(false)
  const [withdrawing, setWithdrawing] = useState(false)

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

  async function handleWithdraw() {
    if (!applicationId) return
    setActionError(null)
    setWithdrawing(true)
    try {
      setApplication(await applicationsApi.withdrawApplication(applicationId))
      toast.info('Application withdrawn.')
    } catch (err) {
      setActionError(getErrorMessage(err))
    } finally {
      setWithdrawing(false)
    }
  }

  const job = application?.job
  const statusView = application ? STATUS_VIEWS[application.status] : null
  const canWithdraw = application?.status === 'submitted' || application?.status === 'under_review'

  return (
    <PageLayout
      title={job?.title ?? 'Application'}
      subtitle={application ? `Applied ${formatDate(application.submittedAt)}` : undefined}
      back={{ to: '/candidate/applications', label: 'Back to applications' }}
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
            <Stack direction="row" spacing={1.5} alignItems="center" sx={{ mb: 2, flexWrap: 'wrap', rowGap: 1 }}>
              <Stack direction="row" spacing={1} alignItems="center" sx={{ minWidth: 0 }}>
                <BusinessOutlined color="action" />
                <Typography variant="h6" component="h2" noWrap>
                  {application.employer?.companyName ?? 'Company no longer available'}
                </Typography>
              </Stack>
              {statusView && <Chip label={statusView.label} size="small" color={statusView.color} sx={{ fontWeight: 600 }} />}
            </Stack>

            <Typography variant="body2" color="text.secondary">
              Submitted {formatDate(application.submittedAt)}
              {application.updatedAt !== application.submittedAt && ` · last updated ${formatDate(application.updatedAt)}`}
            </Typography>

            {application.status === 'rejected' && application.rejectionReason && (
              <Alert severity="info" sx={{ mt: 2 }}>
                <Typography variant="body2" fontWeight={600} gutterBottom>
                  Feedback from {application.employer?.companyName ?? 'the employer'}
                </Typography>
                <Typography variant="body2">{application.rejectionReason}</Typography>
              </Alert>
            )}
            {application.status === 'withdrawn' && (
              <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                You withdrew this application on {formatDate(application.updatedAt)}.
              </Typography>
            )}

            <Divider sx={{ my: 2 }} />

            <Stack direction="row" spacing={1.5} sx={{ flexWrap: 'wrap', rowGap: 1 }}>
              <Button
                startIcon={downloading ? <CircularProgress size={14} color="inherit" /> : <DownloadRounded />}
                onClick={handleDownload}
                disabled={downloading}
                variant="outlined"
              >
                Download CV{application.cvFileName ? ` (${application.cvFileName})` : ''}
              </Button>
              {canWithdraw && (
                <Button
                  onClick={handleWithdraw}
                  disabled={withdrawing}
                  color="warning"
                  variant="outlined"
                >
                  {withdrawing ? 'Withdrawing…' : 'Withdraw application'}
                </Button>
              )}
            </Stack>
          </Card>

          <Card variant="outlined" sx={{ p: layout.cardPadding, mt: 3 }}>
            <Typography variant="h6" gutterBottom>
              Match analysis
            </Typography>
            <MatchReport matchResult={application.match} />
          </Card>

          <CompanyInfoCard employer={application.employer} sx={{ mt: 3 }} />

          {job && (
            <Card variant="outlined" sx={{ p: layout.cardPadding, mt: 3 }}>
              <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
                <InsertDriveFileOutlined color="action" />
                <Typography variant="h6" component="h2">
                  The role you applied for
                </Typography>
              </Stack>

              <Typography variant="subtitle1" gutterBottom>
                {job.title}
              </Typography>
              <Stack direction="row" spacing={2} sx={{ color: 'text.secondary', flexWrap: 'wrap', rowGap: 0.5 }}>
                {job.location && (
                  <Typography variant="body2" sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5 }}>
                    <LocationOnOutlined fontSize="small" />
                    {job.location}
                  </Typography>
                )}
                {job.employmentType && (
                  <Typography variant="body2" sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5 }}>
                    <ScheduleOutlined fontSize="small" />
                    {job.employmentType.replace('-', ' ')}
                  </Typography>
                )}
              </Stack>

              {job.description && (
                <Typography variant="body1" sx={{ mt: 2, whiteSpace: 'pre-line' }}>
                  {job.description}
                </Typography>
              )}

              {job.requiredSkills.length > 0 && (
                <>
                  <Divider sx={{ my: 2 }} />
                  <Typography variant="subtitle2" component="h3" sx={{ mb: 1 }}>
                    Required skills
                  </Typography>
                  <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', rowGap: 1 }}>
                    {job.requiredSkills.map((skill) => (
                      <Chip key={skill} label={skill} variant="outlined" size="small" />
                    ))}
                  </Stack>
                </>
              )}

              <Button
                variant="outlined"
                onClick={() => navigate(`/jobs/${job.id}`)}
                sx={{ mt: 2 }}
              >
                View the job advert
              </Button>
            </Card>
          )}
        </>
      )}
    </PageLayout>
  )
}
