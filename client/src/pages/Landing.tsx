import { Box, Button, Divider, Stack, Typography } from '@mui/material'
import { ArrowForwardRounded } from '@mui/icons-material'
import { Link as RouterLink } from 'react-router-dom'
import { useAuth } from '@/auth/AuthContext'
import EmployerStrip from '@/components/public/EmployerStrip'
import HeroSection from '@/components/public/HeroSection'
import TopJobs from '@/components/public/TopJobs'
import { useLandingJobs } from '@/components/public/useLandingJobs'
import Section from '@/components/public/Section'

/**
 * The public shell — navbar, footer and page chrome — belongs to
 * `PublicLayout`, which owns this route. This page renders body content only.
 *
 * Order is deliberate: the hero carries the feature row inside its own coloured
 * band, then real employers, then real roles, then the two calls to action.
 * Everything sits in one horizontal measure, so the section headings and the
 * navbar and footer share their left and right edges down the whole page.
 *
 * `useLandingJobs` is one request shared by the roles list and the employer
 * strip rather than two, and the strip's employers are de-duplicated from it, so
 * only companies with a live opening can appear.
 */
export default function Landing() {
  const { isAuthenticated } = useAuth()
  const { jobs, employers, loading, error, retry } = useLandingJobs()

  return (
    <>
      <HeroSection />

      <EmployerStrip employers={employers} />

      <TopJobs jobs={jobs} loading={loading} error={error} onRetry={retry} />

      <Section spacing="tight">
        <Stack spacing={{ xs: 5, md: 6 }} sx={{ maxWidth: 640, mx: 'auto', textAlign: 'center' }}>
          <Stack spacing={1.5} alignItems="center">
            <Typography variant="h2" component="h2" sx={{ color: 'text.primary' }}>
              Ready to find your next opportunity?
            </Typography>
            <Typography variant="body1" color="text.secondary">
              Browse open roles, upload one CV, and see exactly how your skills line up with
              each job — including the gaps worth closing before you apply.
            </Typography>
            <Stack
              direction={{ xs: 'column', sm: 'row' }}
              spacing={1.5}
              justifyContent="center"
              sx={{ pt: 0.5, alignItems: 'stretch' }}
            >
              <Button
                component={RouterLink}
                to="/jobs"
                variant="contained"
                size="large"
                endIcon={<ArrowForwardRounded />}
              >
                Browse all jobs
              </Button>
              {!isAuthenticated && (
                <Button component={RouterLink} to="/register" variant="outlined" size="large">
                  Create free account
                </Button>
              )}
            </Stack>
          </Stack>

          <Divider />

          <Stack spacing={1.5} alignItems="center">
            <Typography variant="h2" component="h2" sx={{ color: 'text.primary' }}>
              Post a role in minutes
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Post a role, review applicants against a shared pipeline, and shortlist using
              match scores that show their reasoning — never a decision made for you.
            </Typography>
            <Box sx={{ pt: 0.5 }}>
              <Button
                component={RouterLink}
                to="/register"
                variant="outlined"
                size="large"
                endIcon={<ArrowForwardRounded />}
              >
                Start hiring
              </Button>
            </Box>
          </Stack>
        </Stack>
      </Section>
    </>
  )
}
