import { Container, type SxProps, type Theme } from '@mui/material'
import type { ReactNode } from 'react'
import { layout } from '@/theme'

interface PageContainerProps {
  children: ReactNode
  id?: string
  sx?: SxProps<Theme>
}

/**
 * The single horizontal measure for the whole product.
 *
 * Every band on every page renders its content inside one of these, so the
 * navbar, hero, section headings, footers, listings and forms all start and end
 * on the same x-position — on the landing page and when navigating between
 * pages.
 *
 * Note there is deliberately no `maxWidth` prop. MUI's `Container` offers a
 * breakpoint scale (sm 600 / md 900 / lg 1200 / xl 1536) and the previous code
 * used four of those values across the app, which is exactly how the navbar came
 * to sit outside a 1536px jobs listing. Fixing the width here — and refusing to
 * parameterise it — makes that class of drift a compile error instead of
 * something you have to notice by eye.
 *
 * Pages whose *content* should be narrow (auth card, single-column forms) stay
 * on this container and cap the inner block with `maxWidth` + `mx: 'auto'`, so
 * the outer edges still line up with everything else.
 */
export default function PageContainer({ children, id, sx }: PageContainerProps) {
  return (
    <Container
      id={id}
      maxWidth={false}
      sx={{ maxWidth: layout.container.maxWidth, px: layout.container.px, ...sx }}
    >
      {children}
    </Container>
  )
}
