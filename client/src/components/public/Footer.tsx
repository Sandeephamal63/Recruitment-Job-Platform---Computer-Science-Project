import { Box, Link, Stack, Typography } from '@mui/material'
import PageContainer from '@/components/shared/PageContainer'
import { Link as RouterLink } from 'react-router-dom'
import Brand from '@/components/shared/Brand'
import { neutral } from '@/theme'

export default function Footer() {
  return (
    <Box
      component="footer"
      sx={{
        mt: 'auto',
        py: { xs: 3.5, md: 4.5 },
        borderTop: `1px solid ${neutral[200]}`,
        backgroundColor: 'background.default',
      }}
    >
      <PageContainer>
        <Stack
          direction={{ xs: 'column', sm: 'row' }}
          spacing={2.5}
          justifyContent="space-between"
          alignItems={{ xs: 'flex-start', sm: 'center' }}
        >
          <Brand size="sm" />

          <Stack
            direction={{ xs: 'column', sm: 'row' }}
            spacing={{ xs: 1, sm: 2.5 }}
            alignItems={{ xs: 'flex-start', sm: 'center' }}
          >
            <Typography variant="caption" color="text.secondary">
              &copy; {new Date().getFullYear()} Recruit
            </Typography>
            <Stack direction="row" spacing={2.5}>
              <Link component={RouterLink} to="/jobs" variant="body2" underline="hover" color="text.secondary">
                Browse jobs
              </Link>
              <Link component={RouterLink} to="/register" variant="body2" underline="hover" color="text.secondary">
                Create account
              </Link>
            </Stack>
          </Stack>
        </Stack>
      </PageContainer>
    </Box>
  )
}
