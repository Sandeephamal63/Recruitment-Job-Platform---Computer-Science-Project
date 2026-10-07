import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router-dom'
import { Box, CircularProgress } from '@mui/material'
import { DASHBOARD_PATH, RequireAnonymous, RequireAuth, RequireRole } from '@/auth/RequireAuth'
import { useAuth } from '@/auth/AuthContext'
import AppShell from '@/components/portal/AppShell'
import PublicLayout from '@/components/public/PublicLayout'
import Landing from '@/pages/Landing'
import JobDetail from '@/pages/JobDetail'
import JobList from '@/pages/JobList'
import Login from '@/pages/Login'
import NotFound from '@/pages/NotFound'
import Register from '@/pages/Register'

const EmployerOverview = lazy(() => import('@/pages/employer/Overview'))
const EmployerJobs = lazy(() => import('@/pages/employer/EmployerJobs'))
const EmployerApplicantsIndex = lazy(() => import('@/pages/employer/EmployerApplicantsIndex'))
const CandidateDashboard = lazy(() => import('@/pages/candidate/Dashboard'))
const CandidateApplications = lazy(() => import('@/pages/candidate/Applications'))
const CandidateApplicationDetail = lazy(() => import('@/pages/candidate/ApplicationDetail'))
const CandidateProfile = lazy(() => import('@/pages/CandidateProfile'))
const EmployerProfile = lazy(() => import('@/pages/EmployerProfile'))
const EmployerJobNew = lazy(() => import('@/pages/EmployerJobNew'))
const EmployerJobEdit = lazy(() => import('@/pages/EmployerJobEdit'))
const EmployerApplicants = lazy(() => import('@/pages/EmployerApplicants'))
const EmployerApplicantDetail = lazy(() => import('@/pages/EmployerApplicantDetail'))

function DashboardFallback() {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
      <CircularProgress />
    </Box>
  )
}

function ProtectedRoute({ children, role }: { children: React.ReactNode; role: 'employer' | 'candidate' }) {
  return (
    <RequireRole role={role}>
      <Suspense fallback={<DashboardFallback />}>
        {children}
      </Suspense>
    </RequireRole>
  )
}

/** Auth-only guard. `/dashboard` must not be role-gated: a candidate hitting a
 *  mismatched role guard gets redirected back to `/dashboard`, which loops. */
function ProtectedAnyRole({ children }: { children: React.ReactNode }) {
  return (
    <RequireAuth>
      <Suspense fallback={<DashboardFallback />}>
        {children}
      </Suspense>
    </RequireAuth>
  )
}

function PublicLanding() {
  return <Landing />
}

/** One route for both roles. Registering `/dashboard` once per role made the
 *  second declaration unreachable — react-router takes the first match — so
 *  candidates were always served the employer dashboard. */
function DashboardRoute() {
  const { user } = useAuth()
  if (user?.role === 'candidate') {
    return <CandidateDashboard />
  }
  return <EmployerOverview />
}

export default function App() {
  return (
    <Routes>
      <Route
        path="/login"
        element={
          <RequireAnonymous>
            <Login />
          </RequireAnonymous>
        }
      />
      <Route
        path="/register"
        element={
          <RequireAnonymous>
            <Register />
          </RequireAnonymous>
        }
      />
      <Route element={<PublicLayout />}>
        <Route path="/" element={<PublicLanding />} />
        <Route path="/jobs" element={<JobList />} />
        <Route path="/jobs/:jobId" element={<JobDetail />} />
        <Route path="*" element={<NotFound />} />
      </Route>
      <Route element={<AppShell />}>
        <Route
          path={DASHBOARD_PATH}
          element={
            <ProtectedAnyRole>
              <DashboardRoute />
            </ProtectedAnyRole>
          }
        />
        <Route
          path="/dashboard/jobs"
          element={
            <ProtectedRoute role="employer">
              <EmployerJobs />
            </ProtectedRoute>
          }
        />
        <Route
          path="/dashboard/applicants"
          element={
            <ProtectedRoute role="employer">
              <EmployerApplicantsIndex />
            </ProtectedRoute>
          }
        />
        <Route
          path="/dashboard/profile"
          element={
            <ProtectedRoute role="employer">
              <EmployerProfile />
            </ProtectedRoute>
          }
        />
        <Route
          path="/employer/jobs/new"
          element={
            <ProtectedRoute role="employer">
              <EmployerJobNew />
            </ProtectedRoute>
          }
        />
        <Route
          path="/employer/jobs/:jobId/edit"
          element={
            <ProtectedRoute role="employer">
              <EmployerJobEdit />
            </ProtectedRoute>
          }
        />
        <Route
          path="/employer/jobs/:jobId/applicants"
          element={
            <ProtectedRoute role="employer">
              <EmployerApplicants />
            </ProtectedRoute>
          }
        />
        <Route
          path="/employer/jobs/:jobId/applicants/:applicationId"
          element={
            <ProtectedRoute role="employer">
              <EmployerApplicantDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="/candidate/profile"
          element={
            <ProtectedRoute role="candidate">
              <CandidateProfile />
            </ProtectedRoute>
          }
        />
        <Route
          path="/candidate/applications"
          element={
            <ProtectedRoute role="candidate">
              <CandidateApplications />
            </ProtectedRoute>
          }
        />
        <Route
          path="/candidate/applications/:applicationId"
          element={
            <ProtectedRoute role="candidate">
              <CandidateApplicationDetail />
            </ProtectedRoute>
          }
        />
      </Route>
    </Routes>
  )
}