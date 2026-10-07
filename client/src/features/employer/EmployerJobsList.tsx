import {
  CloseOutlined,
  EditOutlined,
  EventOutlined,
  LocationOnOutlined,
  ReviewsRounded,
  WorkOutlineRounded,
  AddRounded,
} from '@mui/icons-material'
import {
  Alert,
  Box,
  Button,
  Card,
  Chip,
  CircularProgress,
  Divider,
  IconButton,
  Stack,
  Typography,
} from '@mui/material'
import { useState } from 'react'
import { Link as RouterLink } from 'react-router-dom'
import EmptyState from '@/components/shared/EmptyState'
import type { Job } from '@/types/jobs'
import { deadlineView } from '@/utils/dates'

interface EmployerJobsListProps {
  jobs: Job[]
  counts: Record<string, number>
  loading: boolean
  error: string | null
  onRetry: () => void
  onClose: (job: Job) => void
}

/**
 * Three states, not two.
 *
 * Expiry is derived at read time, so a posting past its deadline still *stores*
 * `status: "open"` until `make db-expire-jobs` converges it. This is the one
 * surface where that stored value is shown, so it has to reconcile the two: an
 * employer looking at their own list should not see a role advertised as open
 * that the candidate-facing pages have already hidden.
 */
function StatusChip({ status, expired }: { status: Job['status']; expired: boolean }) {
  if (status === 'closed') {
    return (
      <Chip
        label="Closed"
        size="small"
        color="default"
        variant="outlined"
        sx={{ fontWeight: 600 }}
      />
    )
  }
  if (expired) {
    return (
      <Chip
        label="Deadline passed"
        size="small"
        color="warning"
        variant="outlined"
        sx={{ fontWeight: 600 }}
      />
    )
  }
  return (
    <Chip
      label="Open"
      size="small"
      color="success"
      variant="outlined"
      sx={{ fontWeight: 600 }}
    />
  )
}

export default function EmployerJobsList({ jobs, counts, loading, error, onRetry, onClose }: EmployerJobsListProps) {
  const [closingId, setClosingId] = useState<string | null>(null)

  async function handleClose(job: Job) {
    setClosingId(job.id)
    await onClose(job)
    setClosingId(null)
  }

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
        <CircularProgress />
      </Box>
    )
  }

  if (error) {
    return (
      <Alert
        severity="error"
        action={
          <Button color="inherit" size="small" onClick={onRetry}>
            Retry
          </Button>
        }
      >
        {error}
      </Alert>
    )
  }

  if (jobs.length === 0) {
    return (
      <EmptyState
        icon={<WorkOutlineRounded />}
        title="No job postings yet"
        description="Post your first role to start receiving applications. Applicants are scored against the job description automatically, so you can review fit rather than guess at it."
        action={
          <Button component={RouterLink} to="/employer/jobs/new" variant="contained" startIcon={<AddRounded />} sx={{ width: { xs: '100%', sm: 'auto' } }}>
            Post a job
          </Button>
        }
      />
    )
  }

  return (
    <Stack spacing={2.5}>
      {jobs.map((job) => {
        const closing = closingId === job.id
        const deadline = deadlineView(job.deadline)
        return (
          <Card key={job.id} variant="outlined" sx={{ p: { xs: 2, sm: 2.5 }, borderRadius: 3 }}>
            <Stack direction={{ xs: 'column', sm: 'row' }} alignItems={{ xs: 'stretch', sm: 'flex-start' }} spacing={{ xs: 2, sm: 2.5 }}>
              <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                <Stack direction="row" spacing={1} alignItems={{ xs: 'flex-start', sm: 'center' }} sx={{ flexWrap: 'wrap', rowGap: 0.5 }}>
                  <Box sx={{ minWidth: 0 }}>
                    <Typography variant="h3" component="h2" sx={{ color: 'text.primary', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={job.title}>
                      {job.title}
                    </Typography>
                  </Box>
                  <StatusChip status={job.status} expired={deadline?.expired ?? false} />
                </Stack>
                <Stack
                  direction={{ xs: 'column', sm: 'row' }}
                  spacing={{ xs: 0.5, sm: 2 }}
                  alignItems={{ xs: 'flex-start', sm: 'center' }}
                  sx={{ mt: 0.75, color: 'text.secondary', flexWrap: 'wrap' }}
                >
                  <Typography variant="body2" sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5 }}>
                    <LocationOnOutlined fontSize="small" />
                    {job.location}
                  </Typography>
                  <Typography variant="body2" sx={{ textTransform: 'capitalize' }}>
                    {job.employmentType.replace('-', ' ')}
                  </Typography>
                  {/* Not repeated when expired — the status chip already says so. */}
                  {deadline && !deadline.expired && (
                    <Typography
                      variant="body2"
                      sx={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 0.5,
                        fontWeight: deadline.urgent ? 500 : 400,
                        color: deadline.urgent ? 'warning.main' : 'text.secondary',
                      }}
                    >
                      <EventOutlined fontSize="small" />
                      {deadline.label}
                    </Typography>
                  )}
                </Stack>
              </Box>
              <Stack
                direction={{ xs: 'column', sm: 'row' }}
                spacing={{ xs: 0.75, sm: 1 }}
                alignItems={{ xs: 'stretch', sm: 'center' }}
                sx={{ flexWrap: 'wrap', rowGap: 1, width: { xs: '100%', sm: 'auto' } }}
              >
                <Button
                  component={RouterLink}
                  to={`/employer/jobs/${job.id}/applicants`}
                  size="small"
                  variant="outlined"
                  startIcon={<ReviewsRounded fontSize="small" />}
                  sx={{ width: { xs: '100%', sm: 'auto' } }}
                >
                  Review applicants
                  {counts[job.id] > 0 && ` · ${counts[job.id]}`}
                </Button>
                <IconButton
                  component={RouterLink}
                  to={`/employer/jobs/${job.id}/edit`}
                  size="small"
                  aria-label={`Edit ${job.title}`}
                  sx={{ color: 'text.secondary', alignSelf: { xs: 'flex-start', sm: 'center' } }}
                >
                  <EditOutlined fontSize="small" />
                </IconButton>
                {job.status === 'open' && (
                  <Button
                    size="small"
                    color="warning"
                    startIcon={closing ? <CircularProgress size={14} color="inherit" /> : <CloseOutlined />}
                    onClick={() => handleClose(job)}
                    disabled={closing}
                    sx={{ width: { xs: '100%', sm: 'auto' } }}
                  >
                    Close
                  </Button>
                )}
              </Stack>
            </Stack>
            <Typography
              variant="body2"
              color="text.secondary"
              sx={{
                mt: 1.75,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                display: '-webkit-box',
                WebkitLineClamp: 2,
                WebkitBoxOrient: 'vertical',
              }}
            >
              {job.description}
            </Typography>
            {job.requiredSkills.length > 0 && (
              <>
                <Divider sx={{ my: 2 }} />
                <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', rowGap: 1 }}>
                  {job.requiredSkills.map((skill) => (
                    <Chip key={skill} label={skill} size="small" variant="outlined" />
                  ))}
                </Stack>
              </>
            )}
          </Card>
        )
      })}
    </Stack>
  )
}