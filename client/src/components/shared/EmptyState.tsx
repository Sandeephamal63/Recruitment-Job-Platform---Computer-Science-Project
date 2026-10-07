import { Box, Paper, Stack, Typography } from '@mui/material'
import type { ReactNode } from 'react'
import { brand, elevation, neutral } from '@/theme'

interface EmptyStateProps {
  icon: ReactNode
  title: string
  description: string
  /** One primary next action, rendered as a contained button. */
  action?: ReactNode
  /** Supporting actions, rendered as outlined buttons after the primary. */
  secondaryAction?: ReactNode
  /** Caps the copy column so long messages don't stretch across a wide screen. */
  maxWidth?: number
}

/**
 * Shared empty state. Replaces the ad-hoc dashed-border placeholders that were
 * duplicated per page: one icon tile, one headline, one sentence of guidance
 * and an explicit next action — never a dead end.
 */
export default function EmptyState({
  icon,
  title,
  description,
  action,
  secondaryAction,
  maxWidth = 460,
}: EmptyStateProps) {
  const hasActions = Boolean(action || secondaryAction)

  return (
    <Paper
      variant="outlined"
      sx={{
        p: { xs: 4, sm: 6 },
        textAlign: 'center',
        borderRadius: 3,
        borderStyle: 'solid',
        borderColor: neutral[200],
        boxShadow: elevation[1],
        backgroundColor: brand.paper,
      }}
    >
      <Stack spacing={2} alignItems="center" sx={{ maxWidth, mx: 'auto' }}>
        <Box
          sx={{
            width: 64,
            height: 64,
            borderRadius: 999,
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

        <Typography variant="h3" component="h2" sx={{ color: 'text.primary' }}>
          {title}
        </Typography>

        <Typography variant="body1" color="text.secondary">
          {description}
        </Typography>

        {hasActions && (
          <Stack
            direction={{ xs: 'column', sm: 'row' }}
            spacing={1.5}
            justifyContent="center"
            sx={{ pt: 1, width: { xs: '100%', sm: 'auto' } }}
          >
            {action}
            {secondaryAction}
          </Stack>
        )}
      </Stack>
    </Paper>
  )
}
