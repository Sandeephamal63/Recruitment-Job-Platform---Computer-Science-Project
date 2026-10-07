import type { ReactNode } from 'react'
import {
  AddRounded,
  CloseRounded,
  DashboardOutlined,
  LogoutOutlined,
  MenuOutlined,
  PeopleRounded,
  PersonOutlineRounded,
  WorkOutlineRounded,
} from '@mui/icons-material'
import {
  AppBar,
  Box,
  Button,
  Chip,
  Divider,
  Drawer,
  IconButton,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Stack,
  Toolbar,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material'
import { useState } from 'react'
import { Link as RouterLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '@/auth/AuthContext'
import { brand } from '@/theme'
import Brand from '@/components/shared/Brand'
import Breadcrumbs from '@/components/portal/Breadcrumbs'

const DRAWER_WIDTH = { xs: 280, md: 260 } as const

function initials(name: string): string {
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
    .toUpperCase()
}

/** A destination the sidebar can light up. `match` exists because several
 *  portal routes have no nav item of their own: `/employer/jobs/:jobId/edit`
 *  belongs under "My Jobs" and `/employer/jobs/:jobId/applicants*` under
 *  "Applicants", so a plain prefix test on `path` would leave the sidebar with
 *  nothing highlighted while reading a job's applicants. */
interface NavItem {
  path: string
  label: string
  icon: ReactNode
  match?: RegExp
}

function isActive(item: NavItem, pathname: string): boolean {
  if (item.match) return item.match.test(pathname)
  return pathname === item.path
}

const employerNav: NavItem[] = [
  { path: '/dashboard', label: 'Overview', icon: <DashboardOutlined /> },
  {
    path: '/dashboard/jobs',
    label: 'My Jobs',
    icon: <WorkOutlineRounded />,
    match: /^\/employer\/jobs(\/new|\/[^/]+\/edit)$/,
  },
  {
    path: '/dashboard/applicants',
    label: 'Applicants',
    icon: <PeopleRounded />,
    match: /^\/employer\/jobs\/[^/]+\/applicants(\/[^/]+)?$/,
  },
  { path: '/dashboard/profile', label: 'Profile', icon: <PersonOutlineRounded /> },
]

const candidateNav: NavItem[] = [
  { path: '/dashboard', label: 'Dashboard', icon: <DashboardOutlined /> },
  { path: '/candidate/applications', label: 'Applications', icon: <WorkOutlineRounded /> },
  { path: '/candidate/profile', label: 'Profile', icon: <PersonOutlineRounded /> },
]

function headerCta(role: string | undefined): { to: string; label: string } {
  return role === 'employer'
    ? { to: '/employer/jobs/new', label: 'Post a job' }
    : { to: '/jobs', label: 'Browse jobs' }
}

export default function AppShell() {
  const theme = useTheme()
  const isMobile = useMediaQuery(theme.breakpoints.down('md'))
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false)
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null)

  const dashboardPath = '/dashboard'
  const navItems = user?.role === 'employer' ? employerNav : candidateNav
  const cta = headerCta(user?.role)
  const showBreadcrumbs = location.pathname !== dashboardPath

  const profilePath = user?.role === 'employer' ? '/dashboard/profile' : '/candidate/profile'

  async function handleLogout() {
    setAnchorEl(null)
    setMobileDrawerOpen(false)
    await logout()
    navigate('/login', { replace: true })
  }

  function closeAccountMenu() {
    setAnchorEl(null)
  }

  return (
    <Box sx={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', bgcolor: 'background.default' }}>
      <Box sx={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <Drawer
          variant={isMobile ? 'temporary' : 'permanent'}
          open={isMobile ? mobileDrawerOpen : true}
          onClose={() => setMobileDrawerOpen(false)}
          sx={{
            width: DRAWER_WIDTH,
            flexShrink: 0,
            '& .MuiDrawer-paper': {
              width: DRAWER_WIDTH,
              boxSizing: 'border-box',
              borderRight: `1px solid ${theme.palette.divider}`,
              boxShadow: 'none',
              overflowY: 'auto',
              pt: 2,
            },
          }}
        >
          <Box sx={{ px: 2, pt: 1, pb: 1, display: { xs: 'flex', md: 'none' }, alignItems: 'center', justifyContent: 'space-between' }}>
            <Brand size="sm" />
            <IconButton onClick={() => setMobileDrawerOpen(false)} aria-label="Close navigation menu">
              <CloseRounded />
            </IconButton>
          </Box>
          <Divider sx={{ my: 1, display: { md: 'none' } }} />
          <List disablePadding>
            {navItems.map((item) => {
              const active = isActive(item, location.pathname)
              return (
                <ListItem key={item.path} disablePadding sx={{ mb: 0.5 }}>
                  <ListItemButton
                    component={RouterLink}
                    to={item.path}
                    selected={active}
                    aria-current={active ? 'page' : undefined}
                    onClick={() => setMobileDrawerOpen(false)}
                    sx={{
                      borderRadius: 1,
                      mx: 1,
                      '&.Mui-selected': {
                        bgcolor: `${theme.palette.primary.main}12`,
                        '&:hover': { bgcolor: `${theme.palette.primary.main}1A` },
                        '& .MuiListItemIcon-root': { color: theme.palette.primary.main },
                      },
                    }}
                  >
                    <ListItemIcon>{item.icon}</ListItemIcon>
                    <ListItemText
                      primary={item.label}
                      primaryTypographyProps={{
                        fontWeight: active ? 600 : 500,
                        fontSize: '0.875rem',
                        color: active ? 'primary.main' : undefined,
                      }}
                    />
                  </ListItemButton>
                </ListItem>
              )
            })}
          </List>
        </Drawer>

        <Box sx={{ display: 'flex', flexDirection: 'column', flexGrow: 1, minWidth: 0, bgcolor: 'background.default' }}>
          <AppBar position="sticky" sx={{ zIndex: theme.zIndex.drawer + 1 }}>
            <Toolbar sx={{ minHeight: 64, gap: 2, px: { xs: 1.5, md: 3 } }}>
              <IconButton
                color="inherit"
                edge="start"
                onClick={() => setMobileDrawerOpen(true)}
                sx={{ mr: 1, display: { md: 'none' } }}
                aria-label="Open navigation menu"
              >
                <MenuOutlined />
              </IconButton>
              <Brand />
              <Box sx={{ flexGrow: 1 }} />
              {user && (
                <Button
                  component={RouterLink}
                  to={cta.to}
                  variant="contained"
                  startIcon={user.role === 'employer' ? <AddRounded /> : <WorkOutlineRounded />}
                  sx={{ display: { xs: 'none', sm: 'inline-flex' } }}
                >
                  {cta.label}
                </Button>
              )}
              {user && (
                <>
                  <Button
                    onClick={(event) => setAnchorEl(event.currentTarget)}
                    aria-label="Open account menu"
                    aria-haspopup="menu"
                    aria-expanded={Boolean(anchorEl)}
                    sx={{
                      ml: { xs: 0, sm: 1 },
                      px: 2,
                      py: 0.75,
                      borderRadius: 2,
                      minWidth: 0,
                      gap: 1.5,
                      bgcolor: 'transparent',
                      color: 'text.primary',
                      '&:hover': { bgcolor: 'action.hover' },
                    }}
                  >
                    <Box
                      sx={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        width: 32,
                        height: 32,
                        borderRadius: 2,
                        bgcolor: brand.soft,
                        color: brand.primary,
                        fontSize: '0.75rem',
                        fontWeight: 600,
                      }}
                    >
                      {initials(user.name)}
                    </Box>
                    <Box sx={{ display: { xs: 'none', sm: 'flex' }, alignItems: 'center', gap: 1 }}>
                      <Typography variant="body2" fontWeight={500} noWrap>
                        {user.name}
                      </Typography>
                      <Chip
                        label={user.role}
                        size="small"
                        variant="outlined"
                        color="primary"
                        sx={{ height: 20, fontSize: '0.625rem', fontWeight: 500 }}
                      />
                    </Box>
                  </Button>
                  <Menu
                    anchorEl={anchorEl}
                    open={Boolean(anchorEl)}
                    onClose={closeAccountMenu}
                    anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
                    transformOrigin={{ vertical: 'top', horizontal: 'right' }}
                    slotProps={{
                      paper: {
                        sx: {
                          mt: 1,
                          minWidth: 280,
                          borderRadius: 2,
                          border: `1px solid ${theme.palette.divider}`,
                          boxShadow: theme.shadows[3],
                        },
                      },
                    }}
                  >
                    <Box
                      sx={{
                        px: 2,
                        py: 1.5,
                        borderBottom: `1px solid ${theme.palette.divider}`,
                        bgcolor: 'background.default',
                      }}
                    >
                      <Stack direction="row" spacing={1.5} alignItems="center">
                        <Box
                          sx={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            width: 44,
                            height: 44,
                            borderRadius: 2,
                            bgcolor: brand.soft,
                            color: brand.primary,
                            fontSize: '0.875rem',
                            fontWeight: 600,
                          }}
                        >
                          {initials(user.name)}
                        </Box>
                        <Box sx={{ minWidth: 0, flex: 1 }}>
                          <Typography variant="body1" fontWeight={600} noWrap>
                            {user.name}
                          </Typography>
                          <Stack direction="row" alignItems="center" spacing={1} sx={{ mt: 0.25 }}>
                            <Chip
                              label={user.role}
                              size="small"
                              variant="outlined"
                              color="primary"
                              sx={{ height: 20, fontSize: '0.625rem', fontWeight: 500 }}
                            />
                          </Stack>
                          <Typography variant="caption" color="text.secondary" noWrap component="div">
                            {user.email}
                          </Typography>
                        </Box>
                      </Stack>
                    </Box>
                    <MenuItem
                      onClick={() => {
                        closeAccountMenu()
                        navigate(profilePath)
                      }}
                      sx={{ px: 2, py: 1 }}
                    >
                      <ListItemIcon sx={{ minWidth: 36 }}>
                        <PersonOutlineRounded fontSize="small" />
                      </ListItemIcon>
                      <Typography variant="body2">Profile</Typography>
                    </MenuItem>

                    <MenuItem
                      onClick={() => {
                        closeAccountMenu()
                        navigate(dashboardPath)
                      }}
                      sx={{ px: 2, py: 1 }}
                    >
                      <ListItemIcon sx={{ minWidth: 36 }}>
                        <DashboardOutlined fontSize="small" />
                      </ListItemIcon>
                      <Typography variant="body2">Dashboard</Typography>
                    </MenuItem>
                    <Divider sx={{ mx: 1 }} />
                    <MenuItem onClick={handleLogout} sx={{ px: 2, py: 1, color: 'error.main' }}>
                      <ListItemIcon sx={{ minWidth: 36, color: 'error.main' }}>
                        <LogoutOutlined fontSize="small" />
                      </ListItemIcon>
                      <Typography variant="body2" color="error.main">Sign out</Typography>
                    </MenuItem>
                  </Menu>
                </>
              )}
            </Toolbar>
          </AppBar>

          <Box component="main" sx={{ display: 'flex', flexDirection: 'column', flexGrow: 1, minWidth: 0, bgcolor: 'background.default' }}>
            {showBreadcrumbs && <Breadcrumbs />}
            <Box sx={{ flexGrow: 1, width: '100%', maxWidth: '100%', overflowX: 'hidden' }}>
              <Outlet />
            </Box>
          </Box>
        </Box>
      </Box>
    </Box>
  )
}