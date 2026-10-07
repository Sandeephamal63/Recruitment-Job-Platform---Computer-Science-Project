import { Button, Stack, Typography } from '@mui/material'
import { ArrowBackRounded } from '@mui/icons-material'
import { Link as RouterLink } from 'react-router-dom'
import type { ReactNode } from 'react'
import PageContainer from '@/components/shared/PageContainer'

interface PageLayoutProps {
  children: ReactNode
  title?: string
  subtitle?: string
  /** Overrides the default top padding, in the 8px spacing grid. */
  pt?: number
  /** Overrides the default bottom padding, in the 8px spacing grid. */
  pb?: number
  /** A way back to the parent screen, for pages nested under one. Rendered
   *  above the title so every such page puts it in the same place instead of
   *  hand-rolling a back button. */
  back?: { to: string; label: string }
}

/**
 * Portal page frame: a title block, then the page body, inside the shared
 * container.
 *
 * Portal-only. It is reached from `AppShell`, which is the only shell that
 * renders an authenticated user, and it therefore has no opinion about
 * authentication, routing or navigation chrome.
 *
 * This component used to import `useAuth()`, gate `Breadcrumbs` on the user,
 * and branch on `location.pathname !== '/'` to keep itself off the landing page.
 * All three were symptoms of the public browse pages being built on a portal
 * frame: the branch was dead code (`Landing` never rendered `PageLayout` — it
 * composes `Section` bands itself) and the auth gate made a presentational
 * component depend on who is signed in. Breadcrumbs now belongs to `AppShell`
 * and the public pages use `Section`.
 *
 * There is no `maxWidth` prop. This component previously accepted one and the
 * jobs listing passed `xl` (1536px) while the navbar and footer around it were
 * 1200px, so the page visibly widened when you navigated onto it. Every page
 * now resolves its width from `PageContainer` and nothing else.
 */
export default function PageLayout({ children, title, subtitle, pt, pb, back }: PageLayoutProps) {
  return (
    <PageContainer sx={{ pt: pt ?? { xs: 3, md: 4 }, pb: pb ?? { xs: 6, md: 8 } }}>
      {back && (
        <Button
          component={RouterLink}
          to={back.to}
          startIcon={<ArrowBackRounded />}
          sx={{ mb: 1, ml: -1, color: 'text.secondary' }}
        >
          {back.label}
        </Button>
      )}
      {(title || subtitle) && (
        <Stack spacing={1} sx={{ mb: { xs: 3, md: 4 } }}>
          {title && (
            <Typography variant="h4" component="h1" sx={{ color: 'text.primary' }}>
              {title}
            </Typography>
          )}
          {subtitle && (
            <Typography variant="body1" color="text.secondary" sx={{ maxWidth: 620 }}>
              {subtitle}
            </Typography>
          )}
        </Stack>
      )}
      {children}
    </PageContainer>
  )
}
