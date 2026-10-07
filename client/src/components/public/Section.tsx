import { Box } from '@mui/material'
import type { ReactNode } from 'react'
import PageContainer from '@/components/shared/PageContainer'
import { layout } from '@/theme'

interface SectionProps {
  children: ReactNode
  /** `tight` for stacked blocks inside one page, `default` between page-level bands. */
  spacing?: 'tight' | 'default'
  /** Removes the horizontal container, for full-bleed bands. */
  fullBleed?: boolean
  id?: string
}

/**
 * Vertical rhythm for page bands. Every section on a page takes its vertical
 * padding from `layout.section` so pages share one cadence instead of each
 * inventing `py: 8` / `my: 6` values of its own.
 *
 * Horizontal placement is `PageContainer`'s job, and this component no longer
 * takes a `maxWidth`: a band that could pick its own width is how the landing
 * page ended up with content edges that disagreed with its own navbar.
 */
export default function Section({
  children,
  spacing = 'default',
  fullBleed = false,
  id,
}: SectionProps) {
  const py = spacing === 'tight' ? layout.sectionTight : layout.section
  const px = fullBleed ? undefined : layout.gutter

  const content = fullBleed ? (
    <Box id={id} sx={{ py, px }}>
      {children}
    </Box>
  ) : (
    <PageContainer id={id} sx={{ py, px }}>
      {children}
    </PageContainer>
  )

  return <Box component="section">{content}</Box>
}
