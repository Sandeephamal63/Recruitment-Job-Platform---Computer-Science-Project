import { Box, Paper, Stack, Typography } from '@mui/material'
import type { ReactNode } from 'react'
import Brand from '@/components/shared/Brand'
import PageContainer from '@/components/shared/PageContainer'
import { brand, neutral } from '@/theme'

interface AuthLayoutProps {
  title: string
  subtitle: string
  children: ReactNode
  footer?: ReactNode
}

export default function AuthLayout({ title, subtitle, children, footer }: AuthLayoutProps) {
  return (
    <Box sx={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', bgcolor: 'background.default' }}>
      <Box sx={{ flexGrow: 1, display: 'grid', placeItems: 'center', py: { xs: 4, md: 8 } }}>
        <PageContainer>
          <Stack spacing={3.5} sx={{ maxWidth: 440, mx: 'auto' }}>
            <Box sx={{ display: 'flex', justifyContent: 'center' }}>
              <Brand size="lg" />
            </Box>

            <Paper
              elevation={0}
              sx={{
                p: { xs: 3, sm: 4.5 },
                borderRadius: 3.5,
                border: `1px solid ${neutral[200]}`,
                boxShadow: '0 1px 3px rgba(22, 26, 18, 0.05), 0 10px 24px -14px rgba(22, 26, 18, 0.18)',
                backgroundColor: brand.paper,
              }}
            >
              <Stack spacing={3}>
                <Stack spacing={1}>
                  <Typography variant="h3" component="h1" sx={{ color: 'text.primary' }}>
                    {title}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {subtitle}
                  </Typography>
                </Stack>

                {children}
              </Stack>
            </Paper>

            {footer && <Box sx={{ textAlign: 'center' }}>{footer}</Box>}
          </Stack>
        </PageContainer>
      </Box>
    </Box>
  )
}
