import { zodResolver } from '@hookform/resolvers/zod'
import { Alert, Box, Button, CircularProgress, Stack, Typography } from '@mui/material'
import { useEffect, useState } from 'react'
import { Controller, useForm } from 'react-hook-form'
import { getErrorMessage } from '@/api/errors'
import * as applicationsApi from '@/api/applications'
import * as profileApi from '@/api/profile'
import * as matchingApi from '@/api/matching'
import Dropzone from '@/components/shared/Dropzone'
import MatchReport from '@/features/matching/MatchReport'
import { useToast } from '@/hooks/useToast'
import { applyFormSchemaWithProfileCv, type ApplyFormValuesWithProfile } from '@/schemas/apply'
import type { Application } from '@/types/application'
import type { User } from '@/types/profile'
import type { MatchResult } from '@/types/matching'

interface ApplyFormProps {
  jobId: string
  jobTitle: string
  onApplied: (application: Application) => void
}

export default function ApplyForm({ jobId, jobTitle, onApplied }: ApplyFormProps) {
  const toast = useToast()
  const [profile, setProfile] = useState<User | null>(null)
  const [profileLoading, setProfileLoading] = useState(true)
  const [preview, setPreview] = useState<MatchResult | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const {
    control,
    handleSubmit,
    setValue,
    clearErrors,
    watch,
    formState: { isSubmitting },
  } = useForm<ApplyFormValuesWithProfile>({
    resolver: zodResolver(applyFormSchemaWithProfileCv),
    defaultValues: { cv: undefined, useProfileCv: false },
  })
  const [submitError, setSubmitError] = useState<string | null>(null)
  const useProfileCv = watch('useProfileCv')
  const cv = watch('cv')

  useEffect(() => {
    let active = true
    setProfileLoading(true)
    profileApi
      .getProfile()
      .then((p) => {
        if (active) {
          setProfile(p)
          if (p.hasProfileCv) {
            setValue('useProfileCv', true)
          }
        }
      })
      .catch(() => {
        if (active) setProfile(null)
      })
      .finally(() => {
        if (active) setProfileLoading(false)
      })
    return () => {
      active = false
    }
  }, [setValue])

  useEffect(() => {
    let active = true
    if (profile?.hasProfileCv && (useProfileCv || cv == null)) {
      setPreviewLoading(true)
      setPreviewError(null)
      matchingApi
        .getJobMatchPreview(jobId)
        .then((p) => {
          if (active) setPreview(p)
        })
        .catch((err) => {
          if (active) setPreviewError(getErrorMessage(err))
        })
        .finally(() => {
          if (active) setPreviewLoading(false)
        })
    } else {
      setPreview(null)
      setPreviewError(null)
    }
    return () => {
      active = false
    }
  }, [jobId, profile, useProfileCv, cv])

  async function onSubmit(values: ApplyFormValuesWithProfile) {
    setSubmitError(null)
    if (!values.cv && !values.useProfileCv) return
    try {
      const application = await applicationsApi.createApplication(jobId, values.cv as File, Boolean(values.useProfileCv))
      toast.success('Application submitted successfully!')
      onApplied(application)
    } catch (err) {
      setSubmitError(getErrorMessage(err))
    }
  }

  return (
    <Box component="form" onSubmit={handleSubmit(onSubmit)} noValidate>
      <Stack spacing={2.5}>
        {submitError && <Alert severity="error">{submitError}</Alert>}
        
        <Box>
          <Typography variant="subtitle1" fontWeight={600} component="h3" sx={{ mb: 0.5 }}>
            Apply for {jobTitle}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Upload your CV below. Our matching system will analyze your skills against the job requirements.
          </Typography>
        </Box>

        {profileLoading ? (
          <Box sx={{ display: 'flex', alignItems: 'center', py: 2 }}>
            <CircularProgress size={20} />
            <Typography variant="body2" sx={{ ml: 1 }} color="text.secondary">
              Loading profile...
            </Typography>
          </Box>
        ) : profile?.hasProfileCv ? (
          <Stack spacing={2}>
            <Alert severity="info">
              You have a CV saved in your profile. You can use it for this application or upload a new one.
            </Alert>
            <Controller
              name="useProfileCv"
              control={control}
              render={({ field }) => (
                <Button
                  variant={field.value ? 'contained' : 'outlined'}
                  onClick={() => {
                    field.onChange(!field.value)
                    if (!field.value) {
                      setValue('cv', undefined as unknown as File)
                      clearErrors('cv')
                    }
                  }}
                  disabled={isSubmitting}
                  sx={{ alignSelf: 'flex-start' }}
                >
                  {field.value ? 'Use a different CV' : 'Use my saved profile CV'}
                </Button>
              )}
            />
            {!useProfileCv && (
              <Controller
                name="cv"
                control={control}
                render={({ field, fieldState }) => (
                  <Dropzone
                    accept={{
                      types: [
                        'application/pdf',
                        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                      ],
                      maxSize: 5 * 1024 * 1024,
                    }}
                    onFileSelect={(file) => {
                      field.onChange(file)
                      clearErrors('cv')
                    }}
                    onRemoveExisting={() => {
                      setValue('cv', undefined as unknown as File, { shouldValidate: true })
                    }}
                    existingFileName={field.value?.name}
                    existingFileSize={field.value?.size}
                    error={fieldState.error?.message}
                    onErrorDismiss={() => clearErrors('cv')}
                    disabled={isSubmitting}
                    uploadLabel="Upload your CV"
                    helperText="PDF or DOCX up to 5 MB"
                    compact={false}
                  />
                )}
              />
            )}
          </Stack>
        ) : (
          <Controller
            name="cv"
            control={control}
            render={({ field, fieldState }) => (
              <Dropzone
                accept={{
                  types: [
                    'application/pdf',
                    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                  ],
                  maxSize: 5 * 1024 * 1024,
                }}
                onFileSelect={(file) => {
                  field.onChange(file)
                  clearErrors('cv')
                }}
                onRemoveExisting={() => {
                  setValue('cv', undefined as unknown as File, { shouldValidate: true })
                }}
                existingFileName={field.value?.name}
                existingFileSize={field.value?.size}
                error={fieldState.error?.message}
                onErrorDismiss={() => clearErrors('cv')}
                disabled={isSubmitting}
                uploadLabel="Upload your CV"
                helperText="PDF or DOCX up to 5 MB"
                compact={false}
              />
            )}
          />
        )}

        {(profile?.hasProfileCv && (useProfileCv || cv == null)) && (
          <Box sx={{ mt: 1 }}>
            <MatchReport
              matchResult={preview}
              loading={previewLoading}
              error={previewError}
              onRetry={() => {
                setPreviewLoading(true)
                setPreviewError(null)
                matchingApi
                  .getJobMatchPreview(jobId)
                  .then(setPreview)
                  .catch((err) => setPreviewError(getErrorMessage(err)))
                  .finally(() => setPreviewLoading(false))
              }}
            />
          </Box>
        )}

        <Button
          type="submit"
          variant="contained"
          size="large"
          disabled={isSubmitting}
          startIcon={isSubmitting ? <CircularProgress size={18} color="inherit" /> : undefined}
          sx={{ alignSelf: { xs: 'stretch', sm: 'flex-start' }, px: 4, py: 1.25, borderRadius: 2 }}
        >
          {isSubmitting ? 'Submitting Application…' : 'Submit Application'}
        </Button>
      </Stack>
    </Box>
  )
}