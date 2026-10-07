import { Button } from '@mui/material'
import { Link as RouterLink } from 'react-router-dom'
import { SearchOffRounded } from '@mui/icons-material'
import EmptyState from '@/components/shared/EmptyState'

export default function NotFound() {
  return (
    <EmptyState
      icon={<SearchOffRounded />}
      title="Page not found"
      description="That link doesn't point anywhere. It may have been renamed, or the page may never have existed."
      action={
        <Button component={RouterLink} to="/" variant="contained">
          Back to home
        </Button>
      }
      secondaryAction={
        <Button component={RouterLink} to="/jobs" variant="outlined">
          Browse jobs
        </Button>
      }
    />
  )
}
