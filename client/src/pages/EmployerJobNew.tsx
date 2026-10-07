import { Card } from '@mui/material'
import { useNavigate } from 'react-router-dom'
import { DASHBOARD_PATH } from '@/auth/RequireAuth'
import PageLayout from '@/components/portal/PageLayout'
import { layout } from '@/theme'
import JobForm from '@/features/employer/JobForm'

export default function EmployerJobNew() {
  const navigate = useNavigate()
  return (
    <PageLayout
      title="Post a job"
      subtitle="Describe the role so candidates and the matching engine can find it."
      back={{ to: DASHBOARD_PATH, label: 'Back to dashboard' }}
    >
      <Card variant="outlined" sx={{ p: layout.cardPadding }}>
        <JobForm mode="create" onSaved={() => navigate(DASHBOARD_PATH)} onCancel={() => navigate(DASHBOARD_PATH)} />
      </Card>
    </PageLayout>
  )
}
