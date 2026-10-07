import {
  Breadcrumbs as MuiBreadcrumbs,
  Link,
  Box,
  Typography,
} from '@mui/material'
import { NavigateNextRounded, DashboardOutlined } from '@mui/icons-material'
import { Link as RouterLink, useLocation } from 'react-router-dom'
import { layout, neutral } from '@/theme'

interface Crumb {
  label: string
  href: string
  active: boolean
}

interface TrailCrumb {
  label: string
  href: string | ((pathname: string) => string)
}

const DASHBOARD: TrailCrumb = { label: 'Dashboard', href: '/dashboard' }

const ROUTES: Array<{ pattern: RegExp; trail: TrailCrumb[] }> = [
  // Candidate routes
  {
    pattern: /^\/candidate\/applications$/,
    trail: [DASHBOARD, { label: 'Applications', href: '/candidate/applications' }],
  },
  {
    pattern: /^\/candidate\/applications\/[^/]+$/,
    trail: [
      DASHBOARD,
      { label: 'Applications', href: '/candidate/applications' },
      { label: 'Application Details', href: (pathname) => pathname },
    ],
  },
  {
    pattern: /^\/candidate\/saved$/,
    trail: [DASHBOARD, { label: 'Saved Jobs', href: '/candidate/saved' }],
  },
  {
    pattern: /^\/candidate\/profile$/,
    trail: [DASHBOARD, { label: 'Profile', href: '/candidate/profile' }],
  },

  // Employer main navigation tabs
  {
    pattern: /^\/dashboard\/jobs$/,
    trail: [DASHBOARD, { label: 'My Jobs', href: '/dashboard/jobs' }],
  },
  {
    pattern: /^\/dashboard\/applicants$/,
    trail: [DASHBOARD, { label: 'Applicants', href: '/dashboard/applicants' }],
  },
  {
    pattern: /^\/dashboard\/analytics$/,
    trail: [DASHBOARD, { label: 'Analytics', href: '/dashboard/analytics' }],
  },
  {
    pattern: /^\/dashboard\/profile$/,
    trail: [DASHBOARD, { label: 'Company Profile', href: '/dashboard/profile' }],
  },
  {
    pattern: /^\/dashboard\/settings$/,
    trail: [DASHBOARD, { label: 'Settings', href: '/dashboard/settings' }],
  },

  // Employer job management subroutes
  {
    pattern: /^\/employer\/jobs\/new$/,
    trail: [
      DASHBOARD,
      { label: 'My Jobs', href: '/dashboard/jobs' },
      { label: 'Post a Job', href: '/employer/jobs/new' },
    ],
  },
  {
    pattern: /^\/employer\/jobs\/[^/]+\/edit$/,
    trail: [
      DASHBOARD,
      { label: 'My Jobs', href: '/dashboard/jobs' },
      { label: 'Edit Job', href: (pathname) => pathname },
    ],
  },
  {
    pattern: /^\/employer\/jobs\/[^/]+\/applicants\/[^/]+$/,
    trail: [
      DASHBOARD,
      { label: 'My Jobs', href: '/dashboard/jobs' },
      { label: 'Applicants', href: (pathname) => pathname.replace(/\/[^/]+$/, '') },
      { label: 'Applicant Details', href: (pathname) => pathname },
    ],
  },
  {
    pattern: /^\/employer\/jobs\/[^/]+\/applicants$/,
    trail: [
      DASHBOARD,
      { label: 'My Jobs', href: '/dashboard/jobs' },
      { label: 'Applicants', href: (pathname) => pathname },
    ],
  },
]

function formatFallbackSegment(pathname: string): string {
  const segments = pathname.split('/').filter(Boolean)
  const last = segments[segments.length - 1] ?? 'Overview'
  return last
    .replace(/[-_]/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

function crumbsFor(pathname: string): Crumb[] {
  const match = ROUTES.find((route) => route.pattern.test(pathname))
  const trail: TrailCrumb[] = match
    ? match.trail
    : [
        DASHBOARD,
        {
          label: formatFallbackSegment(pathname),
          href: pathname,
        },
      ]

  return trail.map((crumb, index) => {
    const href = typeof crumb.href === 'function' ? crumb.href(pathname) : crumb.href
    return {
      label: crumb.label,
      href,
      active: index === trail.length - 1,
    }
  })
}

export default function Breadcrumbs() {
  const { pathname } = useLocation()
  const crumbs = crumbsFor(pathname)

  // Don't render redundant single-item trail if root dashboard is reached
  if (crumbs.length <= 1) {
    return null
  }

  return (
    <Box
      sx={{
        py: 1.5,
        px: layout.container.px,
        borderBottom: `1px solid ${neutral[200]}`,
        bgcolor: 'background.default',
      }}
    >
      <MuiBreadcrumbs
        aria-label="breadcrumb"
        separator={<NavigateNextRounded sx={{ fontSize: 16, color: 'text.disabled' }} />}
        sx={{ maxWidth: '100%', overflow: 'hidden' }}
      >
        {crumbs.map((crumb) => {
          const isDashboard = crumb.label === 'Dashboard'

          if (crumb.active) {
            return (
              <Typography
                key={crumb.href}
                variant="body2"
                aria-current="page"
                sx={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  fontWeight: 600,
                  fontSize: '0.8125rem',
                  color: 'text.primary',
                  textOverflow: 'ellipsis',
                  overflow: 'hidden',
                  whiteSpace: 'nowrap',
                  maxWidth: { xs: 140, sm: 220, md: 320 },
                }}
              >
                {isDashboard && <DashboardOutlined sx={{ fontSize: 15, mr: 0.5, color: 'text.secondary' }} />}
                {crumb.label}
              </Typography>
            )
          }

          return (
            <Link
              key={crumb.href}
              component={RouterLink}
              to={crumb.href}
              underline="hover"
              color="text.secondary"
              sx={{
                display: 'inline-flex',
                alignItems: 'center',
                fontWeight: 500,
                fontSize: '0.8125rem',
                textOverflow: 'ellipsis',
                overflow: 'hidden',
                whiteSpace: 'nowrap',
                maxWidth: { xs: 120, sm: 180, md: 280 },
                transition: 'color 0.15s ease',
                '&:hover': {
                  color: 'primary.main',
                },
              }}
            >
              {isDashboard && <DashboardOutlined sx={{ fontSize: 15, mr: 0.5 }} />}
              {crumb.label}
            </Link>
          )
        })}
      </MuiBreadcrumbs>
    </Box>
  )
}
