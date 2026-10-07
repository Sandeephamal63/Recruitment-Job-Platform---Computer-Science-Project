import {
  ExpandMoreRounded,
  FilterAltOffRounded,
  SearchOffRounded,
  SearchRounded,
  SortRounded,
  TuneRounded,
  WorkOutlineRounded,
} from '@mui/icons-material'
import {
  Alert,
  Box,
  Button,
  Card,
  Chip,
  CircularProgress,
  Collapse,
  FormControlLabel,
  InputAdornment,
  MenuItem,
  Pagination,
  Select,
  Skeleton,
  Stack,
  Switch,
  Typography,
} from '@mui/material'
import type { SelectChangeEvent } from '@mui/material'
import Grid from '@mui/material/Grid2'
import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link as RouterLink } from 'react-router-dom'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import { getErrorMessage } from '@/api/errors'
import * as jobsApi from '@/api/jobs'
import { FormSelect, FormTextField } from '@/components/shared/forms'
import EmptyState from '@/components/shared/EmptyState'
import Section from '@/components/public/Section'
import type { Job, JobFilters } from '@/types/jobs'
import { EMPLOYMENT_TYPES, EXPERIENCE_LEVELS } from '@/types/jobs'
import { brand, neutral } from '@/theme'
import { deadlineView } from '@/utils/dates'

const SORT_OPTIONS = [
  { value: 'newest', label: 'Newest first' },
  { value: 'oldest', label: 'Oldest first' },
  { value: 'title', label: 'Title A–Z' },
] as const

type SortValue = (typeof SORT_OPTIONS)[number]['value']

const jobSearchSchema = z.object({
  q: z.string(),
  location: z.string(),
  employmentType: z.union([z.literal(''), z.enum(EMPLOYMENT_TYPES)]),
  experienceLevel: z.union([z.literal(''), z.enum(EXPERIENCE_LEVELS)]),
  remote: z.boolean(),
  salaryMin: z.string(),
  skills: z.string(),
})

type JobSearchValues = z.infer<typeof jobSearchSchema>

const EMPTY_SEARCH: JobSearchValues = {
  q: '',
  location: '',
  employmentType: '',
  experienceLevel: '',
  remote: false,
  salaryMin: '',
  skills: '',
}

function hasActiveFilters(filters: JobFilters): boolean {
  const { sort: _s, page: _p, pageSize: _ps, ...rest } = filters
  return Object.keys(rest).length > 0
}

function filterCount(filters: JobFilters): number {
  const { sort: _s, page: _p, pageSize: _ps, ...rest } = filters
  return Object.keys(rest).length
}

function JobCardSkeleton() {
  return (
    <Card variant="outlined" sx={{ p: { xs: 2, sm: 2.5 }, borderRadius: 3 }}>
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems={{ sm: 'center' }}>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Skeleton width="55%" height={24} />
          <Stack direction="row" spacing={1} sx={{ mt: 0.75 }}>
            <Skeleton variant="rounded" width={64} height={20} />
            <Skeleton variant="rounded" width={80} height={20} />
            <Skeleton variant="rounded" width={72} height={20} />
          </Stack>
          <Skeleton width="90%" sx={{ mt: 1 }} />
        </Box>
        <Skeleton variant="rounded" width={100} height={32} sx={{ flexShrink: 0 }} />
      </Stack>
    </Card>
  )
}

function CompactJobCard({ job }: { job: Job }) {
  const salary =
    job.salaryMin !== null && job.salaryMax !== null
      ? `$${job.salaryMin.toLocaleString()} – $${job.salaryMax.toLocaleString()}`
      : null
  const deadline = deadlineView(job.deadline)

  const postedDate = new Date(job.createdAt)
  const now = new Date()
  const diffDays = Math.floor((now.getTime() - postedDate.getTime()) / (1000 * 60 * 60 * 24))
  const timeAgo =
    diffDays === 0
      ? 'Today'
      : diffDays === 1
        ? '1d ago'
        : diffDays < 7
          ? `${diffDays}d ago`
          : diffDays < 30
            ? `${Math.floor(diffDays / 7)}w ago`
            : `${Math.floor(diffDays / 30)}mo ago`

  return (
    <Card
      variant="outlined"
      sx={{
        p: { xs: 2, sm: 2.5 },
        borderRadius: 3,
        transition: 'box-shadow .18s ease, border-color .18s ease, transform .18s ease',
        '&:hover': { transform: 'translateY(-2px)' },
        '&:focus-within': { borderColor: 'primary.light' },
      }}
    >
      <Stack spacing={1.25}>
        <Stack
          direction={{ xs: 'column', sm: 'row' }}
          spacing={{ xs: 1, sm: 2 }}
          alignItems={{ sm: 'flex-start' }}
          justifyContent="space-between"
        >
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Stack direction="row" spacing={1} alignItems="center">
              <Typography
                variant="h5"
                component="h2"
                sx={{
                  color: 'text.primary',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  minWidth: 0,
                  flex: 1,
                }}
              >
                <Box
                  component={RouterLink}
                  to={`/jobs/${job.id}`}
                  sx={{
                    color: 'inherit',
                    textDecoration: 'none',
                    transition: 'color .16s ease',
                    '&:hover': { color: 'primary.main' },
                  }}
                >
                  {job.title}
                </Box>
              </Typography>
              <Typography
                variant="caption"
                sx={{
                  color: 'text.disabled',
                  flexShrink: 0,
                  display: { xs: 'none', sm: 'block' },
                }}
              >
                {timeAgo}
              </Typography>
            </Stack>

            <Stack
              direction="row"
              spacing={1}
              sx={{
                mt: 0.5,
                color: 'text.secondary',
                flexWrap: 'wrap',
                rowGap: 0.25,
                alignItems: 'center',
              }}
            >
              {job.employer?.companyName && (
                <Typography
                  variant="body2"
                  sx={{
                    fontWeight: 500,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    maxWidth: 200,
                  }}
                >
                  {job.employer.companyName}
                </Typography>
              )}
              {job.employer?.companyName && (
                <Box
                  sx={{
                    width: 3,
                    height: 3,
                    borderRadius: '50%',
                    backgroundColor: neutral[400],
                    flexShrink: 0,
                  }}
                />
              )}
              <Typography variant="body2">{job.location}</Typography>
              <Box
                sx={{
                  width: 3,
                  height: 3,
                  borderRadius: '50%',
                  backgroundColor: neutral[400],
                  flexShrink: 0,
                }}
              />
              <Typography variant="body2" sx={{ textTransform: 'capitalize' }}>
                {job.employmentType.replace('-', ' ')}
              </Typography>
              {salary && (
                <>
                  <Box
                    sx={{
                      width: 3,
                      height: 3,
                      borderRadius: '50%',
                      backgroundColor: neutral[400],
                      flexShrink: 0,
                    }}
                  />
                  <Typography variant="body2" sx={{ color: 'success.main', fontWeight: 500 }}>
                    {salary}
                  </Typography>
                </>
              )}
              {deadline && (
                <>
                  <Box
                    sx={{
                      width: 3,
                      height: 3,
                      borderRadius: '50%',
                      backgroundColor: neutral[400],
                      flexShrink: 0,
                    }}
                  />
                  <Typography
                    variant="body2"
                    sx={{
                      fontWeight: 500,
                      color: deadline.urgent ? 'warning.main' : 'text.secondary',
                    }}
                  >
                    {deadline.label}
                  </Typography>
                </>
              )}
            </Stack>
          </Box>

          <Stack
            direction="row"
            spacing={0.75}
            sx={{
              flexShrink: 0,
              flexWrap: 'wrap',
              rowGap: 0.75,
              alignItems: 'center',
            }}
          >
            {job.remote && <Chip label="Remote" size="small" variant="outlined" />}
            {job.experienceLevel && (
              <Chip
                label={job.experienceLevel.charAt(0).toUpperCase() + job.experienceLevel.slice(1)}
                size="small"
                variant="outlined"
              />
            )}
          </Stack>
        </Stack>

        {job.description && (
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              display: '-webkit-box',
              WebkitLineClamp: 1,
              WebkitBoxOrient: 'vertical',
            }}
          >
            {job.description}
          </Typography>
        )}

        <Stack
          direction="row"
          spacing={1}
          alignItems="center"
          justifyContent="space-between"
        >
          <Stack direction="row" spacing={0.75} sx={{ flexWrap: 'wrap', rowGap: 0.75, minWidth: 0 }}>
            {job.requiredSkills.slice(0, 5).map((skill) => (
              <Chip
                key={skill}
                label={skill}
                size="small"
                sx={{
                  height: 22,
                  fontSize: '0.6875rem',
                  backgroundColor: brand.faint,
                  color: 'primary.main',
                  border: 'none',
                  fontWeight: 600,
                }}
              />
            ))}
            {job.requiredSkills.length > 5 && (
              <Chip
                label={`+${job.requiredSkills.length - 5}`}
                size="small"
                sx={{
                  height: 22,
                  fontSize: '0.6875rem',
                  backgroundColor: neutral[100],
                  color: neutral[600],
                  border: 'none',
                  fontWeight: 600,
                }}
              />
            )}
          </Stack>

          <Button
            component={RouterLink}
            to={`/jobs/${job.id}`}
            variant="outlined"
            size="small"
            sx={{
              flexShrink: 0,
              minWidth: 0,
              px: 2,
              fontSize: '0.8125rem',
            }}
          >
            View details
          </Button>
        </Stack>
      </Stack>
    </Card>
  )
}

export default function JobList() {
  const { control, handleSubmit, reset, watch, setValue, formState } = useForm<JobSearchValues>({
    resolver: zodResolver(jobSearchSchema),
    defaultValues: EMPTY_SEARCH,
  })

  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [pagination, setPagination] = useState({
    page: 1,
    pageSize: 12,
    total: 0,
    totalPages: 1,
    hasNext: false,
    hasPrevious: false,
  })
  const [filters, setFilters] = useState<JobFilters>({})
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  const [sort, setSort] = useState<SortValue>('newest')

  useEffect(() => {
    let active = true
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const result = await jobsApi.listOpenJobs({
          ...filters,
          sort,
          page: pagination.page,
          pageSize: pagination.pageSize,
        })
        if (active) {
          setJobs(result.jobs)
          setPagination((prev) => ({
            ...prev,
            total: result.total,
            totalPages: result.totalPages,
            hasNext: result.hasNext,
            hasPrevious: result.hasPrevious,
          }))
        }
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
  }, [filters, pagination.page, pagination.pageSize, reloadKey, sort])

  const onSubmit = (values: JobSearchValues) => {
    const next: JobFilters = {}
    if (values.q.trim()) next.q = values.q.trim()
    if (values.location.trim()) next.location = values.location.trim()
    if (values.employmentType) next.employmentType = values.employmentType
    if (values.experienceLevel) next.experienceLevel = values.experienceLevel
    if (values.remote) next.remote = true
    if (values.salaryMin.trim()) {
      const parsed = Number(values.salaryMin)
      if (Number.isFinite(parsed)) next.salaryMin = parsed
    }
    const skills = values.skills
      .split(',')
      .map((skill) => skill.trim())
      .filter(Boolean)
    if (skills.length) next.skills = skills

    setFilters(next)
    setPagination((prev) => ({ ...prev, page: 1 }))
  }

  const onClear = () => {
    reset(EMPTY_SEARCH)
    setFilters({})
    setPagination((prev) => ({ ...prev, page: 1 }))
  }

  const handlePageChange = (_event: React.ChangeEvent<unknown>, page: number) => {
    setPagination((prev) => ({ ...prev, page }))
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const filtersActive = hasActiveFilters(filters)
  const activeCount = filterCount(filters)
  const pending = formState.isSubmitting || loading

  const rangeStart = (pagination.page - 1) * pagination.pageSize + 1
  const rangeEnd = Math.min(pagination.page * pagination.pageSize, pagination.total)

  return (
    <Section spacing="tight">
      <Stack spacing={1} sx={{ mb: { xs: 2, md: 3 } }}>
        <Stack direction="row" spacing={1.5} alignItems="center">
          <WorkOutlineRounded sx={{ color: 'primary.main', fontSize: 28 }} />
          <Typography variant="h4" component="h1" sx={{ color: 'text.primary' }}>
            Browse jobs
          </Typography>
        </Stack>
        <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 520, pl: 0.25 }}>
          Find open roles and apply with your CV — your match score appears instantly.
        </Typography>
      </Stack>

      <Stack spacing={2}>
        <Card
          variant="outlined"
          sx={{ p: { xs: 2, sm: 2.5 }, borderRadius: 3, position: 'relative', zIndex: 1 }}
        >
          <form onSubmit={handleSubmit(onSubmit)} noValidate>
            <Stack spacing={2}>
              <Grid container spacing={1.5} alignItems="flex-end">
                <Grid size={{ xs: 12, sm: 5, md: 4 }}>
                  <FormTextField<JobSearchValues>
                    name="q"
                    control={control}
                    label="Search"
                    placeholder="Job title or keyword"
                    size="small"
                    fullWidth
                    slotProps={{
                      input: {
                        startAdornment: (
                          <InputAdornment position="start">
                            <SearchRounded fontSize="small" sx={{ color: 'text.disabled' }} />
                          </InputAdornment>
                        ),
                      },
                    }}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 4, md: 3 }}>
                  <FormTextField<JobSearchValues>
                    name="location"
                    control={control}
                    label="Location"
                    placeholder="City or remote"
                    size="small"
                    fullWidth
                  />
                </Grid>
                <Grid size={{ xs: 6, sm: 3, md: 2.5 }}>
                  <FormSelect<JobSearchValues>
                    name="employmentType"
                    control={control}
                    label="Job type"
                    size="small"
                    fullWidth
                  >
                    <MenuItem value="">Any type</MenuItem>
                    {EMPLOYMENT_TYPES.map((type) => (
                      <MenuItem key={type} value={type} sx={{ textTransform: 'capitalize' }}>
                        {type.replace('-', ' ')}
                      </MenuItem>
                    ))}
                  </FormSelect>
                </Grid>
                <Grid size={{ xs: 6, sm: 'auto' }} sx={{ display: 'flex', gap: 1 }}>
                  <Button
                    type="submit"
                    variant="contained"
                    size="small"
                    startIcon={
                      loading ? <CircularProgress size={14} color="inherit" /> : <SearchRounded />
                    }
                    disabled={loading}
                    sx={{ minWidth: 0, px: 2 }}
                  >
                    {loading ? 'Searching…' : 'Search'}
                  </Button>
                </Grid>
              </Grid>

              <Stack
                direction="row"
                spacing={1}
                alignItems="center"
                sx={{ borderTop: `1px solid ${neutral[200]}`, pt: 1.5 }}
              >
                <Button
                  onClick={() => setShowAdvanced((value) => !value)}
                  size="small"
                  color="secondary"
                  startIcon={<TuneRounded sx={{ fontSize: '1rem !important' }} />}
                  endIcon={
                    <ExpandMoreRounded
                      sx={{
                        transition: 'transform .2s ease',
                        transform: showAdvanced ? 'rotate(180deg)' : 'none',
                        fontSize: '1rem !important',
                      }}
                    />
                  }
                  aria-expanded={showAdvanced}
                  aria-controls="job-advanced-filters"
                  sx={{ fontSize: '0.8125rem' }}
                >
                  More filters
                </Button>
                {activeCount > 0 && (
                  <Chip
                    label={`${activeCount} active`}
                    size="small"
                    onDelete={onClear}
                    sx={{
                      height: 22,
                      fontSize: '0.6875rem',
                      fontWeight: 700,
                      backgroundColor: brand.faint,
                      color: 'primary.main',
                      '& .MuiChip-deleteIcon': {
                        color: 'primary.main',
                        fontSize: '0.875rem',
                        '&:hover': { color: 'primary.dark' },
                      },
                    }}
                  />
                )}
                <Box sx={{ flex: 1 }} />
                {filtersActive && (
                  <Button
                    onClick={onClear}
                    disabled={pending}
                    size="small"
                    color="secondary"
                    startIcon={<FilterAltOffRounded sx={{ fontSize: '1rem !important' }} />}
                    sx={{ fontSize: '0.8125rem' }}
                  >
                    Clear all
                  </Button>
                )}
              </Stack>

              <Collapse in={showAdvanced} unmountOnExit>
                <Grid container spacing={1.5} id="job-advanced-filters">
                  <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                    <FormSelect<JobSearchValues>
                      name="experienceLevel"
                      control={control}
                      label="Experience"
                      size="small"
                      fullWidth
                    >
                      <MenuItem value="">Any level</MenuItem>
                      {EXPERIENCE_LEVELS.map((level) => (
                        <MenuItem
                          key={level}
                          value={level}
                          sx={{ textTransform: 'capitalize' }}
                        >
                          {level}
                        </MenuItem>
                      ))}
                    </FormSelect>
                  </Grid>
                  <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                    <FormTextField<JobSearchValues>
                      name="salaryMin"
                      type="number"
                      control={control}
                      label="Min salary"
                      placeholder="e.g. 60000"
                      size="small"
                      fullWidth
                      slotProps={{ htmlInput: { min: 0, step: 1000 } }}
                    />
                  </Grid>
                  <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                    <FormTextField<JobSearchValues>
                      name="skills"
                      control={control}
                      label="Skills"
                      placeholder="React, TypeScript"
                      helperText="Comma separated"
                      size="small"
                      fullWidth
                    />
                  </Grid>
                  <Grid
                    size={{ xs: 12, sm: 6, md: 3 }}
                    sx={{ display: 'flex', alignItems: 'center' }}
                  >
                    <FormControlLabel
                      control={
                        <Switch
                          checked={watch('remote')}
                          onChange={(event) =>
                            setValue('remote', event.target.checked, { shouldDirty: true })
                          }
                          color="primary"
                          size="small"
                        />
                      }
                      label={
                        <Typography variant="body2" color="text.secondary">
                          Remote only
                        </Typography>
                      }
                      sx={{
                        ml: 0,
                        px: 1.5,
                        py: 0.5,
                        borderRadius: 2,
                        '&:hover': { backgroundColor: neutral[50] },
                      }}
                    />
                  </Grid>
                </Grid>
              </Collapse>
            </Stack>
          </form>
        </Card>

        {error && (
          <Alert
            severity="error"
            action={
              <Button
                color="inherit"
                size="small"
                onClick={() => setReloadKey((key) => key + 1)}
              >
                Retry
              </Button>
            }
          >
            {error}
          </Alert>
        )}

        {loading && (
          <Stack spacing={1.5}>
            <Skeleton width={200} height={20} />
            {[0, 1, 2, 3].map((index) => (
              <JobCardSkeleton key={index} />
            ))}
          </Stack>
        )}

        {!loading && !error && jobs.length === 0 && (
          <EmptyState
            icon={<SearchOffRounded />}
            title={filtersActive ? 'No jobs match these filters' : 'No open jobs yet'}
            description={
              filtersActive
                ? 'Try removing a filter or broadening your search to see more results.'
                : 'There are no open roles right now. Check back soon or create an account to stay notified.'
            }
            action={
              filtersActive ? (
                <Button
                  variant="contained"
                  onClick={onClear}
                  startIcon={<FilterAltOffRounded />}
                >
                  Clear filters
                </Button>
              ) : (
                <Button component={RouterLink} to="/register" variant="contained">
                  Create an account
                </Button>
              )
            }
          />
        )}

        {!loading && !error && jobs.length > 0 && (
          <Stack spacing={1.5}>
            <Stack
              direction="row"
              spacing={1.5}
              alignItems="center"
              justifyContent="space-between"
              sx={{ px: 0.25 }}
            >
              <Typography variant="body2" color="text.secondary">
                Showing{' '}
                <Box component="span" sx={{ color: 'text.primary', fontWeight: 600 }}>
                  {rangeStart}–{rangeEnd}
                </Box>{' '}
                of{' '}
                <Box component="span" sx={{ color: 'text.primary', fontWeight: 600 }}>
                  {pagination.total}
                </Box>{' '}
                {pagination.total === 1 ? 'job' : 'jobs'}
              </Typography>

              <Stack direction="row" spacing={0.5} alignItems="center">
                <SortRounded sx={{ color: 'text.disabled', fontSize: 18 }} />
                <Select
                  value={sort}
                  onChange={(e: SelectChangeEvent) => {
                    setSort(e.target.value as SortValue)
                    setPagination((prev) => ({ ...prev, page: 1 }))
                  }}
                  size="small"
                  variant="outlined"
                  sx={{
                    minWidth: 140,
                    '& .MuiOutlinedInput-notchedOutline': { border: 'none' },
                    '& .MuiSelect-select': {
                      py: 0.5,
                      fontSize: '0.8125rem',
                      fontWeight: 600,
                      color: neutral[700],
                    },
                  }}
                >
                  {SORT_OPTIONS.map((opt) => (
                    <MenuItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </MenuItem>
                  ))}
                </Select>
              </Stack>
            </Stack>

            {jobs.map((job) => (
              <CompactJobCard key={job.id} job={job} />
            ))}

            {pagination.totalPages > 1 && (
              <Stack
                direction={{ xs: 'column', sm: 'row' }}
                spacing={1}
                alignItems="center"
                justifyContent="space-between"
                sx={{ pt: 1 }}
              >
                <Typography variant="caption" color="text.disabled">
                  Page {pagination.page} of {pagination.totalPages}
                </Typography>
                <Pagination
                  count={pagination.totalPages}
                  page={pagination.page}
                  onChange={handlePageChange}
                  color="primary"
                  shape="rounded"
                  showFirstButton
                  showLastButton
                  boundaryCount={1}
                  siblingCount={1}
                  size="small"
                />
              </Stack>
            )}
          </Stack>
        )}
      </Stack>
    </Section>
  )
}
