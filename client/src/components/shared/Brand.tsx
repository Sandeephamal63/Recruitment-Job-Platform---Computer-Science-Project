import { Box, Link, Typography } from '@mui/material'
import { Link as RouterLink } from 'react-router-dom'
import BrandMark from '@/components/shared/BrandMark'

interface BrandProps {
  to?: string
  /** Renders the wordmark in `text.primary` — for use on light surfaces. */
  size?: 'sm' | 'md' | 'lg'
}

/** The one place the product name is written. Every surface — public header,
 *  app bar, auth pages, footers, browser tab — resolves to "Recruit". */
export default function Brand({ to = '/', size = 'md' }: BrandProps) {
  const mark = { sm: 28, md: 32, lg: 40 }[size]
  const wordVariant = size === 'lg' ? 'h5' : 'subtitle1'

  return (
    <Link
      component={RouterLink}
      to={to}
      underline="none"
      aria-label="Recruit home"
      sx={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 1.25,
        borderRadius: 2,
        transition: 'opacity .16s ease',
        '&:hover': { opacity: 0.85 },
      }}
    >
      <Box sx={{ lineHeight: 0, display: 'flex' }}>
        <BrandMark size={mark} />
      </Box>
      <Typography
        variant={wordVariant}
        sx={{ color: 'text.primary', fontWeight: 700, letterSpacing: '-0.015em' }}
      >
        Recruit
      </Typography>
    </Link>
  )
}
