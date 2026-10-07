import { FilterListRounded, DownloadRounded } from '@mui/icons-material'
import {
  Alert, Box, Button, Card, Chip, CircularProgress, Dialog, DialogActions, DialogContent,
  DialogTitle, FormControl, InputLabel, MenuItem, Select, Stack, TableCell, TableContainer,
  TableHead, TableRow, TableBody, TableSortLabel, TablePagination, TextField, Tooltip,
  Typography, IconButton,
} from '@mui/material'
import PageLayout from '@/components/portal/PageLayout'
import AvatarImage from '@/components/shared/AvatarImage'
import { useCallback, useEffect, useState } from 'react'
import { Link as RouterLink, useParams } from 'react-router-dom'
import * as applicationsApi from '@/api/applications'
import { getJob } from '@/api/jobs'
import { getErrorMessage } from '@/api/errors'
import type { Application, ApplicationStatus } from '@/types/application'
import type { Job } from '@/types/jobs'
import MatchReport from '@/features/matching/MatchReport'
import { layout } from '@/theme'

const STATUS_OPTIONS: { value: ApplicationStatus; label: string }[] = [
  { value: 'submitted', label: 'Submitted' },
  { value: 'under_review', label: 'Under review' },
  { value: 'shortlisted', label: 'Shortlisted' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'withdrawn', label: 'Withdrawn' },
]

const SORT_OPTIONS = [
  { value: 'newest', label: 'Newest first' },
  { value: 'oldest', label: 'Oldest first' },
  { value: 'score-desc', label: 'Score: high to low' },
  { value: 'score-asc', label: 'Score: low to high' },
]

function StatusChip({ status }: { status: ApplicationStatus }) {
  const colors: Record<ApplicationStatus, 'default' | 'info' | 'success' | 'error' | 'warning'> = {
    submitted: 'default',
    under_review: 'info',
    shortlisted: 'success',
    rejected: 'error',
    withdrawn: 'warning',
  }
  return (
    <Chip
      label={status.replace('_', ' ')}
      size="small"
      color={colors[status]}
      variant="outlined"
      sx={{ fontWeight: 600, textTransform: 'capitalize', height: 24 }}
    />
  )
}

function StatusUpdateDialog({
  open,
  onClose,
  application,
  onStatusChange,
  loading,
}: {
  open: boolean
  onClose: () => void
  application: Application
  onStatusChange: (application: Application, status: ApplicationStatus, reason?: string) => void
  loading: boolean
}) {
  const [status, setStatus] = useState<ApplicationStatus>(application.status)
  const [showReason, setShowReason] = useState(false)
  const [reason, setReason] = useState(application.rejectionReason || '')

  const requiresReason = status === 'rejected'

  const handleSubmit = () => {
    if (requiresReason && !reason.trim()) {
      setShowReason(true)
      return
    }
    onStatusChange(application, status, requiresReason ? reason.trim() : undefined)
    onClose()
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Update status for {application.candidate?.name || 'candidate'}</DialogTitle>
      <DialogContent>
        <FormControl fullWidth sx={{ mt: 1, mb: 2 }}>
          <InputLabel id="status-label">Status</InputLabel>
          <Select
            labelId="status-label"
            value={status}
            label="Status"
            onChange={(e) => {
              const newStatus = e.target.value as ApplicationStatus
              setStatus(newStatus)
              setShowReason(newStatus === 'rejected')
            }}
          >
            {STATUS_OPTIONS.map((opt) => (
              <MenuItem key={opt.value} value={opt.value}>
                {opt.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        {showReason && (
          <TextField
            multiline
            rows={3}
            fullWidth
            label="Rejection reason (required)"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Explain why this candidate was not selected..."
            sx={{ mt: 1 }}
            error={requiresReason && !reason.trim()}
            helperText={requiresReason && !reason.trim() ? 'A rejection reason is required' : undefined}
          />
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} disabled={loading}>
          Cancel
        </Button>
        <Button
          variant="contained"
          color={status === 'rejected' ? 'error' : 'primary'}
          onClick={handleSubmit}
          disabled={loading}
        >
          {status === 'rejected' ? 'Reject' : 'Update'}
        </Button>
      </DialogActions>
    </Dialog>
  )
}

export default function EmployerApplicants() {
  const { jobId } = useParams<{ jobId: string }>()
  const [job, setJob] = useState<Job | null>(null)
  const [applications, setApplications] = useState<Application[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(25)
  const [total, setTotal] = useState(0)
  const [sort, setSort] = useState<'newest' | 'oldest' | 'score-desc' | 'score-asc'>('newest')
  const [filterStatus, setFilterStatus] = useState<ApplicationStatus | ''>('')
  const [minScore, setMinScore] = useState<number | ''>('')

  const [statusDialog, setStatusDialog] = useState<{ open: boolean; application: Application | null }>({ open: false, application: null })

  const load = useCallback(async () => {
    if (!jobId) return
    setLoading(true)
    setError(null)
    try {
      const [fetchedJob, fetched] = await Promise.all([
        getJob(jobId),
        applicationsApi.listApplicants({
          jobId,
          status: filterStatus || undefined,
          minScore: minScore || undefined,
          sort,
          page: page + 1,
          pageSize,
        }),
      ])
      setJob(fetchedJob)
      setApplications(fetched.applications)
      setTotal(fetched.pagination.total)
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [jobId, page, pageSize, sort, filterStatus, minScore])

  useEffect(() => {
    load()
  }, [load])

  const handleStatusChange = useCallback(
    async (application: Application, newStatus: ApplicationStatus, reason?: string) => {
      try {
        await applicationsApi.updateApplicationStatus(application.id, newStatus, reason)
        setApplications((prev) =>
          prev.map((app) => (app.id === application.id ? { ...app, status: newStatus, rejectionReason: reason ?? app.rejectionReason } : app))
        )
      } catch (err) {
        setError(getErrorMessage(err))
      }
    },
    []
  )

  const handleOpenStatusDialog = (app: Application) => {
    setStatusDialog({ open: true, application: app })
  }

  return (
    <PageLayout
      title={job ? `${job.title} · applicants` : 'Applicants'}
      subtitle="Review applications and progress the best candidates through your pipeline."
      back={{ to: '/dashboard/jobs', label: 'Back to my job postings' }}
    >
      {loading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress />
        </Box>
      )}

      {!loading && error && (
        <Alert severity="error" action={<Button color="inherit" size="small" onClick={load}>Retry</Button>}>
          {error}
        </Alert>
      )}

      {!loading && !error && applications.length === 0 && (
        <Card variant="outlined" sx={{ p: layout.cardPadding, textAlign: 'center' }}>
          <Typography variant="h6" gutterBottom>
            No applicants yet
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Applications will appear here once candidates apply.
          </Typography>
        </Card>
      )}

      {!loading && !error && applications.length > 0 && (
        <>
          <Card variant="outlined" sx={{ p: layout.cardPadding, overflow: 'hidden' }}>
            <TableContainer sx={{ maxHeight: 600 }}>
              <TableHead>
                <TableRow>
                  <TableCell>
                    <Tooltip title="Sort by candidate name">
                      <TableSortLabel
                        active={sort === 'newest'}
                        direction="asc"
                        onClick={() => setSort('newest')}
                      >
                        Candidate
                      </TableSortLabel>
                    </Tooltip>
                  </TableCell>
                  <TableCell>
                    <Tooltip title="Sort by match score">
                      <TableSortLabel
                        active={sort === 'score-desc'}
                        direction="desc"
                        onClick={() => setSort('score-desc')}
                      >
                        Match score
                      </TableSortLabel>
                    </Tooltip>
                  </TableCell>
                  <TableCell>
                    <Tooltip title="Sort by status">
                      <TableSortLabel
                        active={sort === 'newest'}
                        direction="asc"
                        onClick={() => setSort('newest')}
                      >
                        Status
                      </TableSortLabel>
                    </Tooltip>
                  </TableCell>
                  <TableCell>
                    <Tooltip title="Sort by date">
                      <TableSortLabel
                        active={sort === 'newest'}
                        direction="desc"
                        onClick={() => setSort('newest')}
                      >
                        Submitted
                      </TableSortLabel>
                    </Tooltip>
                  </TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {applications.map((app) => (
                  <TableRow key={app.id} hover>
                    <TableCell>
                      <Stack direction="row" spacing={1.5} alignItems="center">
                        <AvatarImage
                          applicationId={app.id}
                          name={app.candidate?.name || 'Unknown'}
                          size={34}
                          alt=""
                        />
                        <Box sx={{ minWidth: 0 }}>
                          <Typography variant="body2" fontWeight={500} noWrap>
                            {app.candidate?.name || 'Unknown'}
                          </Typography>
                          <Typography variant="caption" color="text.secondary" noWrap display="block">
                            {app.candidate?.email || '—'}
                          </Typography>
                        </Box>
                      </Stack>
                    </TableCell>
                    <TableCell>
                      <MatchReport matchResult={app.match} variant="compact" />
                    </TableCell>
                    <TableCell>
                      <StatusChip status={app.status} />
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="text.secondary">
                        {new Date(app.submittedAt).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}
                      </Typography>
                    </TableCell>
                    <TableCell align="right">
                      <Tooltip title="Review application">
                        <Button
                          component={RouterLink}
                          to={`/employer/jobs/${jobId}/applicants/${app.id}`}
                          size="small"
                          startIcon={<IconButton component="span" sx={{ p: 0 }}><DownloadRounded fontSize="small" /></IconButton>}
                        >
                          Review
                        </Button>
                      </Tooltip>
                      <Tooltip title="Update status">
                        <IconButton
                          size="small"
                          onClick={() => handleOpenStatusDialog(app)}
                          sx={{ ml: 0.5 }}
                        >
                          <FilterListRounded fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </TableContainer>
            <TablePagination
              rowsPerPageOptions={[25, 50]}
              component="div"
              count={total}
              rowsPerPage={pageSize}
              page={page}
              onPageChange={(_: unknown, newPage: number) => setPage(newPage)}
              onRowsPerPageChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                setPageSize(Number(e.target.value))
                setPage(0)
              }}
            />
          </Card>

          <Stack direction="row" spacing={2} alignItems="center" sx={{ mt: 2, flexWrap: 'wrap' }}>
            <FormControl size="small" sx={{ minWidth: 160 }}>
              <InputLabel id="status-filter">Status</InputLabel>
              <Select
                labelId="status-filter"
                value={filterStatus}
                label="Status"
                onChange={(e) => {
                  setFilterStatus(e.target.value as ApplicationStatus)
                  setPage(0)
                }}
              >
                <MenuItem value="">{'All statuses'}</MenuItem>
                {STATUS_OPTIONS.map((opt) => (
                  <MenuItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControl size="small" sx={{ minWidth: 180 }}>
              <InputLabel id="sort-select">Sort by</InputLabel>
              <Select
                labelId="sort-select"
                value={sort}
                label="Sort by"
                onChange={(e) => {
                  setSort(e.target.value as typeof sort)
                  setPage(0)
                }}
              >
                {SORT_OPTIONS.map((opt) => (
                  <MenuItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField
              size="small"
              type="number"
              label="Min score"
              value={minScore}
              onChange={(e) => {
                setMinScore(e.target.value === '' ? '' : Number(e.target.value))
                setPage(0)
              }}
              inputProps={{ min: 0, max: 100, step: 1 }}
              sx={{ minWidth: 140 }}
            />
          </Stack>
        </>
      )}

      {statusDialog.open && statusDialog.application && (
        <StatusUpdateDialog
          open={statusDialog.open}
          onClose={() => setStatusDialog({ open: false, application: null })}
          application={statusDialog.application}
          onStatusChange={handleStatusChange}
          loading={loading}
        />
      )}
    </PageLayout>
  )
}