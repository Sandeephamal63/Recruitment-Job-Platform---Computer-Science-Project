import { Grid, Stack, Typography } from '@mui/material'
import { Groups, Search, TrendingUp, WorkOutline } from '@mui/icons-material'

interface Feature {
  icon: typeof WorkOutline
  title: string
  body: string
}

const FEATURES: Feature[] = [
  {
    icon: WorkOutline,
    title: 'Post and manage jobs',
    body: 'Structured listings with required skills, salary band, experience level and location.',
  },
  {
    icon: Search,
    title: 'CV-to-job matching',
    body: 'Every application is scored 0–100 on skills overlap, with the gaps called out.',
  },
  {
    icon: Groups,
    title: 'Candidate profiles',
    body: 'Upload a CV once, tag your skills, and apply to any role with a single click.',
  },
  {
    icon: TrendingUp,
    title: 'Funnel analytics',
    body: 'Live applicant pipeline with status tracking — under review, shortlisted, or rejected.',
  },
]

const ICON_SIZE = 22

/**
 * What the platform does, as four plain text columns.
 *
 * Renders a bare `Grid` and nothing else — no `Section`, no container, no
 * background of its own. It is drawn by `HeroSection` inside the hero's own
 * coloured band, so the background runs unbroken from the headline through the
 * buttons to here. When this owned a section of its own, the join between the
 * two read as a seam across the page.
 *
 * Icons sit directly above each heading at a small, fixed size. An earlier pass
 * put each one in a tinted circle, and at four across, four circles plus four
 * boxes of text gave the row more visual weight than the hero headline.
 */
export default function FeatureRow() {
  return (
    <Grid container spacing={{ xs: 3, md: 4 }}>
      {FEATURES.map((feature) => {
        const Icon = feature.icon
        return (
          <Grid key={feature.title} item xs={12} sm={6} md={3}>
            <Stack spacing={0.75}>
              <Icon sx={{ fontSize: ICON_SIZE, color: 'text.secondary' }} aria-hidden />
              <Typography variant="h5" component="h2" sx={{ color: 'text.primary' }}>
                {feature.title}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {feature.body}
              </Typography>
            </Stack>
          </Grid>
        )
      })}
    </Grid>
  )
}
