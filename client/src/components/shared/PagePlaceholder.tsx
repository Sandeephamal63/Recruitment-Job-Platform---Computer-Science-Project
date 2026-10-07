import { Box, Chip, Typography } from '@mui/material'
import PageContainer from '@/components/shared/PageContainer'
import { HourglassEmptyRounded } from '@mui/icons-material'
import type { ReactNode } from 'react'
import { brand } from '@/theme'

interface PagePlaceholderProps {
  title: string
  description: string
  badge?: string
  icon?: ReactNode
  /** Where the user should go next. A placeholder that cannot be left is a
   *  dead end, so every route that uses one supplies this. */
  action?: ReactNode
}

/** Placeholder for a route that exists but has no content yet. Distinct from
 *  `EmptyState`, which means "there is no data" and always offers a way out. */
export default function PagePlaceholder({
  title,
  description,
  badge,
  icon = <HourglassEmptyRounded />,
  action,
}: PagePlaceholderProps) {
  return (
    <PageContainer sx={{ py: { xs: 6, md: 10 } }}>
      <Box sx={{ textAlign: 'center', maxWidth: 440, mx: 'auto' }}>
        <Box
          sx={{
            width: 64,
            height: 64,
            borderRadius: 999,
            mx: 'auto',
            mb: 2.5,
            display: 'grid',
            placeItems: 'center',
            color: brand.primary,
            backgroundColor: brand.faint,
            border: `1px solid ${brand.soft}`,
            '& svg': { fontSize: 30 },
          }}
        >
          {icon}
        </Box>
        {badge && (
          <Box sx={{ mb: 1.5 }}>
            <Chip label={badge} size="small" color="primary" variant="outlined" />
          </Box>
        )}
        <Typography variant="h3" component="h1" sx={{ color: 'text.primary', mb: 1 }}>
          {title}
        </Typography>
        <Typography variant="body1" color="text.secondary">
          {description}
        </Typography>
        {action && <Box sx={{ mt: 3 }}>{action}</Box>}
      </Box>
    </PageContainer>
  )
}
