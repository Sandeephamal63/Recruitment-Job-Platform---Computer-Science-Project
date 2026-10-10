import { Box, Button, Chip, Stack, Typography } from '@mui/material'
import { SearchRounded } from '@mui/icons-material'
import { Link as RouterLink } from 'react-router-dom'
import { useAuth } from '@/auth/AuthContext'
import { DASHBOARD_PATH } from '@/auth/RequireAuth'
import FeatureRow from '@/components/public/FeatureRow'
import Section from '@/components/public/Section'
import { brand, neutral } from '@/theme'

/**
 * The hero band, and the feature row inside it.
 *
 * The gradient runs from the top of this section all the way through the
 * headline, the CTAs and the feature row below, with nothing interrupting it.
 * `FeatureRow` is rendered here rather than by the page because it shares this
 * background — when it was a sibling section it needed its own container and
 * padding, and the join between the two read as a seam.
 */
export default function HeroSection() {
  const { isAuthenticated } = useAuth()

  return (
    <Box
      component="section"
      sx={{
        background: `linear-gradient(180deg, ${brand.cream} 0%, ${brand.tint} 100%)`,
        borderBottom: `1px solid ${neutral[200]}`,
      }}
    >
      <Section spacing="tight">
        <Stack spacing={3} alignItems="center" textAlign="center" sx={{ maxWidth: 700, mx: 'auto' }}>
          <Chip
            label="Recruit makes better matches"
            size="small"
            variant="outlined"
            sx={{
              color: brand.primary,
              borderColor: brand.soft,
              backgroundColor: brand.faint,
              fontWeight: 500,
            }}
          />

          <Typography variant="h1" component="h1" sx={{ color: 'text.primary' }}>
            Every application, scored and explained
          </Typography>

          <Typography
            variant="body1"
            sx={{
              color: 'text.secondary',
              maxWidth: 580,
              fontSize: { xs: '0.9375rem', md: '1rem' },
            }}
          >
            Recruit connects employers with candidates and scores each CV against the job
            description — surfacing matched skills, missing skills and what to do next, for
            both sides of the table.
          </Typography>

          <Stack
            direction={{ xs: 'column', sm: 'row' }}
            spacing={1.5}
            alignItems="stretch"
            justifyContent="center"
            sx={{ width: { xs: '100%', sm: 'auto' } }}
          >
            <Button
              component={RouterLink}
              to={isAuthenticated ? DASHBOARD_PATH : '/jobs'}
              variant="contained"
              size="large"
              startIcon={<SearchRounded />}
            >
              {isAuthenticated ? 'Go to dashboard' : 'Browse open jobs'}
            </Button>
            {!isAuthenticated && (
              <Button
                component={RouterLink}
                to="/register"
                variant="outlined"
                size="large"
                sx={{ bgcolor: 'transparent' }}
              >
                Create free account
              </Button>
            )}
          </Stack>

          {!isAuthenticated && (
            <Typography variant="caption" color="text.secondary">
              Already have an account?{' '}
              <Box
                component={RouterLink}
                to="/login"
                sx={{ color: 'text.primary', fontWeight: 500, textDecoration: 'underline' }}
              >
                Sign in
              </Box>
            </Typography>
          )}
        </Stack>

        <Box sx={{ mt: { xs: 5, md: 7 } }}>
          <FeatureRow />
        </Box>
      </Section>
    </Box>
  )
}
