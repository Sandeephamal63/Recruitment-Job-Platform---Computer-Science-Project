import { Box, Button, Grid, Skeleton, Stack, Typography } from '@mui/material'
import { ArrowForwardRounded, WorkOutlineRounded } from '@mui/icons-material'
import { Link as RouterLink } from 'react-router-dom'
import Section from '@/components/public/Section'
import { neutral } from '@/theme'
import type { Job } from '@/types/jobs'

interface TopJobsProps {
  jobs: Job[]
  loading: boolean
  error: string | null
  onRetry: () => void
}

/**
 * Recently posted roles, as a dense list.
 *
 * A border and nothing else: no shadow, no tinted fill. Each row is a single
 * clickable strip rather than a card, because at this density the chrome starts
 * to compete with the job titles, which are the only thing worth reading here.
 */
export default function TopJobs({ jobs, loading, error, onRetry }: TopJobsProps) {
  return (
    <Section spacing="tight">
      <Stack spacing={2}>
        <Stack
          direction={{ xs: 'column', sm: 'row' }}
          justifyContent="space-between"
          alignItems={{ xs: 'flex-start', sm: 'baseline' }}
          spacing={1}
        >
          <Typography variant="h2" component="h2" sx={{ color: 'text.primary' }}>
            Latest roles
          </Typography>
          <Button
            component={RouterLink}
            to="/jobs"
            size="small"
            endIcon={<ArrowForwardRounded />}
            sx={{ alignSelf: 'flex-start' }}
          >
            View all jobs
          </Button>
        </Stack>

        {loading && (
          <Stack spacing={1.25} aria-busy>
            {[0, 1, 2, 3].map((index) => (
              <Skeleton key={index} variant="rounded" height={68} />
            ))}
          </Stack>
        )}

        {!loading && error && (
          <Stack spacing={1.5} alignItems="flex-start">
            <Typography variant="body2" color="text.secondary">
              {error}
            </Typography>
            <Button size="small" variant="outlined" onClick={onRetry}>
              Try again
            </Button>
          </Stack>
        )}

        {!loading && !error && jobs.length === 0 && (
          <Typography variant="body2" color="text.secondary">
            No open roles just yet.{' '}
            <Box component={RouterLink} to="/jobs" sx={{ color: 'text.primary', textDecoration: 'underline' }}>
              Browse the board
            </Box>{' '}
            to see everything posted.
          </Typography>
        )}

        {!loading && !error && jobs.length > 0 && (
          <Grid container spacing={1.5}>
            {jobs.map((job) => (
              <Grid key={job.id} item xs={12} md={6}>
                <Box
                  component={RouterLink}
                  to={`/jobs/${job.id}`}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1.5,
                    px: 2,
                    py: 1.5,
                    border: `1px solid ${neutral[200]}`,
                    borderRadius: 2,
                    textDecoration: 'none',
                    color: 'inherit',
                    transition: 'border-color .16s ease, background-color .16s ease',
                    '&:hover': {
                      borderColor: neutral[400],
                      backgroundColor: neutral[50],
                    },
                  }}
                >
                  <WorkOutlineRounded sx={{ fontSize: 20, color: 'text.disabled', flexShrink: 0 }} />
                  <Box sx={{ minWidth: 0, flexGrow: 1 }}>
                    <Typography variant="subtitle2" noWrap sx={{ color: 'text.primary' }}>
                      {job.title}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" noWrap>
                      {[
                        job.employer?.companyName,
                        job.location,
                        job.employmentType.replace('-', ' '),
                      ]
                        .filter(Boolean)
                        .join(' · ')}
                    </Typography>
                  </Box>
                  <ArrowForwardRounded
                    sx={{ fontSize: 18, color: 'text.disabled', flexShrink: 0 }}
                  />
                </Box>
              </Grid>
            ))}
          </Grid>
        )}
      </Stack>
    </Section>
  )
}
