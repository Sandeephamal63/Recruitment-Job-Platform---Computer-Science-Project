import { zodResolver } from '@hookform/resolvers/zod'
import { Alert, Box, Button, Card, Chip, CircularProgress, Divider, MenuItem, Stack, Typography } from '@mui/material'
import Grid from '@mui/material/Grid2'
import PageLayout from '@/components/portal/PageLayout'
import Dropzone from '@/components/shared/Dropzone'
import { SaveOutlined } from '@mui/icons-material'
import { useCallback, useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router-dom'
import { getErrorMessage } from '@/api/errors'
import * as profileApi from '@/api/profile'
import CompanyMark from '@/components/shared/CompanyMark'
import { FormSelect, FormTextField } from '@/components/shared/forms'
import { DASHBOARD_PATH } from '@/auth/RequireAuth'
import { useToast } from '@/hooks/useToast'
import { layout } from '@/theme'
import {
  COMPANY_SIZES,
  LOGO_ACCEPT,
  employerProfileSchema,
  emptyEmployerProfile,
  type EmployerProfileValues,
} from '@/schemas/profile'
import type { User } from '@/types/profile'

export default function EmployerProfile() {
  const toast = useToast()
  const [profile, setProfile] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [logoError, setLogoError] = useState<string | null>(null)
  const [logoBusy, setLogoBusy] = useState(false)

  const {
    control,
    handleSubmit,
    reset,
    formState: { isSubmitting },
  } = useForm<EmployerProfileValues>({
    resolver: zodResolver(employerProfileSchema),
    defaultValues: emptyEmployerProfile(),
  })

  const loadProfile = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await profileApi.getProfile()
      setProfile(data)
      reset({
        name: data.name ?? '',
        companyName: data.companyName ?? '',
        companySize: (data.companySize as EmployerProfileValues['companySize']) || '11-50',
        companyIndustry: data.companyIndustry ?? '',
        companyDescription: data.companyDescription ?? '',
      })
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [reset])

  useEffect(() => {
    loadProfile()
  }, [loadProfile])

  const onSubmit = async (values: EmployerProfileValues) => {
    setError(null)
    try {
      setProfile(await profileApi.updateProfile(values))
      toast.success('Profile updated successfully!')
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }

  const handleRemoveLogo = async () => {
    setLogoBusy(true)
    setError(null)
    try {
      setProfile(await profileApi.deleteCompanyLogo())
      toast.info('Company logo removed.')
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLogoBusy(false)
    }
  }

  const handleLogoUpload = useCallback(async (file: File) => {
    setLogoError(null)
    setLogoBusy(true)
    try {
      await profileApi.uploadCompanyLogo(file)
      setProfile(await profileApi.getProfile())
      toast.success('Company logo uploaded!')
    } catch (err) {
      setLogoError(getErrorMessage(err))
    } finally {
      setLogoBusy(false)
    }
  }, [toast])

  if (loading) {
    return (
      <PageLayout title="Employer Profile" subtitle="Manage your company information">
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress />
        </Box>
      </PageLayout>
    )
  }

  if (!profile || profile.role !== 'employer') {
    return (
      <PageLayout title="Employer Profile" subtitle="Manage your company information">
        <Alert severity="error">Employer profile not found</Alert>
      </PageLayout>
    )
  }

  const hasLogo = Boolean(profile.companyLogoUrl)

  return (
    <PageLayout title="Employer Profile" subtitle="Manage your company information">
      {error && (
        <Alert severity="error" onClose={() => setError(null)} sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      <Card variant="outlined" sx={{ p: layout.cardPadding }}>
          <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 3, flexWrap: 'wrap' }}>
            <CompanyMark name={profile.companyName || profile.name} logoUrl={profile.companyLogoUrl} size={64} />
            <Stack sx={{ minWidth: 0 }}>
              <Typography variant="h6">{profile.companyName || 'Your Company'}</Typography>
              <Typography variant="body2" color="text.secondary">
                {profile.email}
              </Typography>
              <Chip label="Employer" size="small" color="primary" variant="outlined" sx={{ mt: 1 }} />
            </Stack>
          </Stack>

          <Divider sx={{ mb: 3 }} />

          <Box component="form" onSubmit={handleSubmit(onSubmit)} noValidate>
            <Stack spacing={3}>
              <Box>
                <Typography variant="subtitle1" sx={{ mb: 0.5 }}>
                  Company logo
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
                  {hasLogo
                    ? `Showing ${profile.companyLogoFileName || 'your uploaded logo'}. It appears beside every job you post.`
                    : 'Optional. Without a logo, candidates see your company initials instead.'}
                </Typography>
                <Dropzone
                  accept={LOGO_ACCEPT}
                  onFileSelect={handleLogoUpload}
                  busy={logoBusy}
                  error={logoError || undefined}
                  onErrorDismiss={() => setLogoError(null)}
                  helperText="PNG, JPEG, WEBP or SVG, max 1 MB"
                  existingFileName={profile.companyLogoFileName ?? undefined}
                  onRemoveExisting={handleRemoveLogo}
                  uploadLabel="Upload logo"
                  disabled={isSubmitting}
                />
              </Box>

              <Divider />

              <Grid container spacing={3}>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <FormTextField
                    name="companyName"
                    control={control}
                    label="Company Name"
                    required
                    disabled={isSubmitting}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <FormSelect
                    name="companySize"
                    control={control}
                    label="Company Size"
                    required
                    disabled={isSubmitting}
                  >
                    {COMPANY_SIZES.map((size) => (
                      <MenuItem key={size} value={size}>
                        {size} employees
                      </MenuItem>
                    ))}
                  </FormSelect>
                </Grid>
                <Grid size={{ xs: 12 }}>
                  <FormTextField
                    name="companyDescription"
                    control={control}
                    label="Company Description"
                    multiline
                    rows={3}
                    required
                    disabled={isSubmitting}
                    placeholder="Describe your company, mission, culture..."
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <FormTextField
                    name="companyIndustry"
                    control={control}
                    label="Industry"
                    disabled={isSubmitting}
                    placeholder="e.g. Software, Healthcare, Finance"
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <FormTextField name="name" control={control} label="Your Name" disabled={isSubmitting} />
                </Grid>
              </Grid>

              <Stack direction="row" spacing={2} justifyContent="flex-end">
                <Button component={Link} to={DASHBOARD_PATH} disabled={isSubmitting}>
                  Back to Dashboard
                </Button>
                <Button
                  type="submit"
                  variant="contained"
                  disabled={isSubmitting}
                  startIcon={isSubmitting ? <CircularProgress size={18} color="inherit" /> : <SaveOutlined />}
                >
                  {isSubmitting ? 'Saving…' : 'Save Changes'}
                </Button>
              </Stack>
            </Stack>
          </Box>
        </Card>
    </PageLayout>
  )
}
