import { Box, Stack, Typography } from '@mui/material'
import { keyframes } from '@emotion/react'
import Section from '@/components/public/Section'
import CompanyMark from '@/components/shared/CompanyMark'
import { neutral } from '@/theme'
import type { EmployerSummary } from '@/types/profile'

interface EmployerStripProps {
  employers: EmployerSummary[]
}

const MIN_DURATION_SECONDS = 22
const MAX_DURATION_SECONDS = 60
const SECONDS_PER_EMPLOYER = 5

/**
 * Actually defined this time. The previous marquee animated a keyframe name that
 * was never registered, so nothing moved and its two copies of the same list sat
 * stacked on top of each other.
 */
const scroll = keyframes`
  from { transform: translateX(0); }
  to { transform: translateX(-100%); }
`

/**
 * Companies hiring right now, as a slow, quiet strip.
 *
 * The list is rendered twice, the second copy `aria-hidden` so screen readers
 * hear it once. Each copy slides left by exactly 100% of *its own* width, which
 * is what makes the loop seamless: copy two arrives precisely where copy one
 * started, showing identical pixels, so the wrap is invisible. And because the
 * two copies always overlap in the middle, there is no gap to scroll through at
 * any point in the cycle — a two-employer database still fills the strip.
 *
 * Note what is *not* animated here: a single wrapping track translating -50%.
 * A block-level flex row is width-constrained to its parent, so a percentage
 * transform on it resolves against that narrower box rather than against the
 * 2208px of content it holds, and the loop ends in a visible jump. Animating the
 * copies sidesteps that because a transform percentage always resolves against
 * the element's own border box.
 *
 * The whole thing is CSS: no timers, no scroll bookkeeping, nothing to leak on
 * unmount. Hover and keyboard focus pause it so the logos can be read, and
 * `prefers-reduced-motion` replaces it with a plain scrollable row.
 */
export default function EmployerStrip({ employers }: EmployerStripProps) {
  if (employers.length === 0) {
    return null
  }

  const duration = Math.min(
    MAX_DURATION_SECONDS,
    Math.max(MIN_DURATION_SECONDS, employers.length * SECONDS_PER_EMPLOYER),
  )

  const copyStyles = {
    display: 'flex',
    alignItems: 'center',
    gap: { xs: 4, md: 6 },
    justifyContent: 'space-evenly',
    px: { xs: 2, md: 3 },
    minWidth: '100%',
    flexShrink: 0,
    animation: `${scroll} ${duration}s linear infinite`,
    willChange: 'transform',
  } as const

  const reduceMotion = {
    '@media (prefers-reduced-motion: reduce)': {
      animation: 'none',
    },
  } as const

  return (
    <Section spacing="tight">
      <Stack spacing={1.5}>
        <Typography variant="caption" color="text.secondary" sx={{ letterSpacing: '0.06em' }}>
          COMPANIES HIRING ON RECRUIT
        </Typography>

        <Box
          sx={{
            display: 'flex',
            overflow: 'hidden',
            '&:hover > *, &:focus-within > *': { animationPlayState: 'paused' },
            '@media (prefers-reduced-motion: reduce)': {
              overflowX: 'auto',
              scrollbarWidth: 'thin',
            },
            borderTop: `1px solid ${neutral[200]}`,
            borderBottom: `1px solid ${neutral[200]}`,
            py: 2,
          }}
        >
          {[false, true].map((isCopy) => (
            <Box
              key={String(isCopy)}
              aria-hidden={isCopy || undefined}
              sx={{ ...copyStyles, ...reduceMotion }}
            >
              {employers.map((employer) => (
                <CompanyMark
                  key={employer.id}
                  name={employer.companyName}
                  logoUrl={employer.companyLogoUrl}
                  size={40}
                  withName
                />
              ))}
            </Box>
          ))}
        </Box>
      </Stack>
    </Section>
  )
}
