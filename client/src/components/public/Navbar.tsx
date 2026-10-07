import { Box, Button, Stack, Toolbar } from '@mui/material'
import PageContainer from '@/components/shared/PageContainer'
import { Link as RouterLink, useLocation } from 'react-router-dom'
import { useAuth } from '@/auth/AuthContext'
import { DASHBOARD_PATH } from '@/auth/RequireAuth'
import Brand from '@/components/shared/Brand'
import { brand, neutral } from '@/theme'

export default function Navbar() {
  const { isAuthenticated } = useAuth()
  const location = useLocation()
  const onJobs = location.pathname === '/jobs' || location.pathname.startsWith('/jobs/')

  return (
    <Box
      component="header"
      sx={{
        position: 'sticky',
        top: 0,
        zIndex: 1100,
        backgroundColor: 'rgba(252, 253, 243, 0.88)',
        backdropFilter: 'saturate(180%) blur(12px)',
        borderBottom: `1px solid ${neutral[200]}`,
      }}
    >
      <PageContainer>
        <Toolbar disableGutters sx={{ minHeight: { xs: 60, md: 68 }, gap: 2 }}>
          <Brand />

          <Stack
            component="nav"
            direction="row"
            spacing={0.5}
            alignItems="center"
            sx={{ display: { xs: 'none', md: 'flex' }, ml: 2 }}
          >
            <Box
              component={RouterLink}
              to="/jobs"
              aria-current={onJobs ? 'page' : undefined}
              sx={{
                px: 1.5,
                py: 0.75,
                borderRadius: 2,
                textDecoration: 'none',
                fontSize: '0.9375rem',
                fontWeight: 600,
                color: onJobs ? 'text.primary' : 'text.secondary',
                backgroundColor: onJobs ? brand.faint : 'transparent',
                transition: 'color .16s ease, background-color .16s ease',
                '&:hover': { color: 'text.primary', backgroundColor: neutral[100] },
              }}
            >
              Jobs
            </Box>
          </Stack>

          <Box sx={{ flexGrow: 1 }} />

          {isAuthenticated ? (
            <Button component={RouterLink} to={DASHBOARD_PATH} variant="contained" size="small">
              Dashboard
            </Button>
          ) : (
            <Stack direction="row" spacing={1} alignItems="center">
              <Button
                component={RouterLink}
                to="/login"
                color="secondary"
                size="small"
                sx={{ px: 2 }}
              >
                Sign in
              </Button>
              <Button component={RouterLink} to="/register" variant="contained" size="small" sx={{ px: 2.5 }}>
                Get started
              </Button>
            </Stack>
          )}
        </Toolbar>
      </PageContainer>
    </Box>
  )
}
