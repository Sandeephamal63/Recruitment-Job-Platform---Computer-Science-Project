import {
  ArrowForwardRounded,
  BusinessOutlined,
  LocationOnOutlined,
  ScheduleOutlined,
} from '@mui/icons-material'
import { Box, Button, Card, Chip, Stack, Typography } from '@mui/material'
import Grid from '@mui/material/Grid2'
import { Link as RouterLink } from 'react-router-dom'
import type { Job } from '@/types/jobs'
import { deadlineView } from '@/utils/dates'

export default function JobCard({ job }: { job: Job }) {
  const salary =
    job.salaryMin !== null && job.salaryMax !== null
      ? `$${job.salaryMin.toLocaleString()} – $${job.salaryMax.toLocaleString()}`
      : null
  const deadline = deadlineView(job.deadline)

  return (
    <Card
      variant="outlined"
      sx={{
        p: { xs: 2.5, sm: 3 },
        borderRadius: 3,
        transition: 'box-shadow .18s ease, border-color .18s ease, transform .18s ease',
        '&:hover': { transform: 'translateY(-2px)' },
        '&:focus-within': { borderColor: 'primary.light' },
      }}
    >
      <Grid container spacing={2.5} alignItems="flex-start">
        <Grid size={{ xs: 12, sm: 8 }} sx={{ minWidth: 0 }}>
          <Stack spacing={1.25}>
            <Typography variant="h3" component="h2" sx={{ color: 'text.primary' }}>
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

            <Stack
              direction="row"
              spacing={1.5}
              sx={{ color: 'text.secondary', flexWrap: 'wrap', rowGap: 0.5 }}
            >
              <Typography variant="body2" sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5 }}>
                <LocationOnOutlined fontSize="small" />
                {job.location}
              </Typography>
              <Typography variant="body2" sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5 }}>
                <ScheduleOutlined fontSize="small" />
                {job.employmentType.replace('-', ' ')}
              </Typography>
              {job.employer?.companyName && (
                <Typography
                  variant="body2"
                  sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5, minWidth: 0 }}
                >
                  <BusinessOutlined fontSize="small" />
                  <Box component="span" sx={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {job.employer.companyName}
                  </Box>
                </Typography>
              )}
            </Stack>
          </Stack>
        </Grid>

        <Grid size={{ xs: 12, sm: 4 }} sx={{ display: 'flex', justifyContent: { sm: 'flex-end' } }}>
          <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap' }}>
            {job.remote && <Chip label="Remote" size="small" variant="outlined" />}
            {job.experienceLevel && (
              <Chip
                label={job.experienceLevel.charAt(0).toUpperCase() + job.experienceLevel.slice(1)}
                size="small"
                variant="outlined"
              />
            )}
            {salary && <Chip label={salary} size="small" variant="outlined" color="success" />}
            {/* The label carries the meaning, so the colour is never the only signal. */}
            {deadline && (
              <Chip
                label={deadline.label}
                size="small"
                color={deadline.urgent ? 'warning' : 'default'}
                variant="outlined"
              />
            )}
          </Stack>
        </Grid>
      </Grid>

      {job.requiredSkills.length > 0 && (
        <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', rowGap: 1, mt: 2 }}>
          {job.requiredSkills.slice(0, 8).map((skill) => (
            <Chip key={skill} label={skill} size="small" variant="outlined" />
          ))}
          {job.requiredSkills.length > 8 && (
            <Chip label={`+${job.requiredSkills.length - 8}`} size="small" variant="outlined" />
          )}
        </Stack>
      )}

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

      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        spacing={1.5}
        alignItems={{ xs: 'stretch', sm: 'center' }}
        justifyContent="flex-end"
        sx={{ mt: 2.5 }}
      >
        <Button component={RouterLink} to={`/jobs/${job.id}`} variant="outlined" size="small">
          View details
        </Button>
        <Button
          component={RouterLink}
          to={`/jobs/${job.id}`}
          variant="contained"
          size="small"
          endIcon={<ArrowForwardRounded />}
        >
          View and apply
        </Button>
      </Stack>
    </Card>
  )
}
