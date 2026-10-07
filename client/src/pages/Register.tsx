import {
  BusinessOutlined,
  EmailOutlined,
  LockOutlined,
  PersonOutlineRounded,
  VisibilityOffOutlined,
  VisibilityOutlined,
  WorkOutlineRounded,
} from '@mui/icons-material'
import {
  Alert,
  Button,
  CircularProgress,
  IconButton,
  InputAdornment,
  Link,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material'
import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect, useRef, useState } from 'react'
import { useForm, type FieldPath } from 'react-hook-form'
import { Link as RouterLink, useNavigate } from 'react-router-dom'
import { getErrorDetails, getErrorMessage } from '@/api/errors'
import { useAuth } from '@/auth/AuthContext'
import { DASHBOARD_PATH } from '@/auth/RequireAuth'
import AuthLayout from '@/components/auth/AuthLayout'
import { FormTextField } from '@/components/shared/forms'
import { registerSchema, type RegisterValues } from '@/schemas/auth'
import type { RegisterPayload } from '@/types/auth'
import { brand, neutral } from '@/theme'

/** Fields the server can address a validation error to. `role` is excluded: it is
 *  not an input, so a message about it belongs in the banner. */
const FIELDS = ['name', 'companyName', 'headline', 'email', 'password'] as const

function toPayload(values: RegisterValues): RegisterPayload {
  const payload: RegisterPayload = {
    role: values.role,
    name: values.name,
    email: values.email,
    password: values.password,
  }
  if (values.role === 'employer') {
    payload.companyName = values.companyName
  } else {
    payload.headline = values.headline
  }
  return payload
}

export default function Register() {
  const { register } = useAuth()
  const navigate = useNavigate()

  const [showPassword, setShowPassword] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const alertRef = useRef<HTMLDivElement>(null)
  const {
    control,
    watch,
    setValue,
    handleSubmit,
    setError,
    clearErrors,
    formState: { isSubmitting },
  } = useForm<RegisterValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { role: 'candidate', name: '', companyName: '', headline: '', email: '', password: '' },
  })

  const role = watch('role')

  useEffect(() => {
    const subscription = watch(() => setSubmitError(null))
    return () => subscription.unsubscribe()
  }, [watch])

  useEffect(() => {
    if (submitError) alertRef.current?.focus()
  }, [submitError])

  async function onSubmit(values: RegisterValues) {
    setSubmitError(null)
    clearErrors([...FIELDS])
    try {
      await register(toPayload(values))
      navigate(DASHBOARD_PATH, { replace: true })
    } catch (err) {
      for (const detail of getErrorDetails(err)) {
        if (FIELDS.includes(detail.field as (typeof FIELDS)[number])) {
          setError(detail.field as FieldPath<RegisterValues>, { type: 'server', message: detail.message })
        }
      }
      setSubmitError(getErrorMessage(err))
    }
  }

  return (
    <AuthLayout
      title="Create your account"
      subtitle="Join as a candidate or an employer."
      footer={
        <Typography variant="body2" color="text.secondary">
          Already have an account?{' '}
          <Link component={RouterLink} to="/login">
            Log in
          </Link>
        </Typography>
      }
    >
      <form onSubmit={handleSubmit(onSubmit)} noValidate>
        <Stack spacing={2.5}>
          {submitError && (
            <Alert severity="error" ref={alertRef} tabIndex={-1}>
              {submitError}
            </Alert>
          )}
          <Stack spacing={1}>
            <ToggleButtonGroup
              value={role}
              exclusive
              onChange={(_, next: 'employer' | 'candidate' | null) => {
                if (next) setValue('role', next, { shouldValidate: true })
              }}
              fullWidth
              size="small"
              role="radiogroup"
              aria-label="Account type"
              sx={{
                p: 0.5,
                borderRadius: 999,
                backgroundColor: neutral[100],
                gap: 0.5,
                '& .MuiToggleButtonGroup-grouped': {
                  border: 0,
                  borderRadius: '999px !important',
                  py: 1,
                  px: 2,
                  color: 'text.secondary',
                  '&.Mui-selected': {
                    backgroundColor: brand.paper,
                    color: brand.primary,
                    '&:hover': { backgroundColor: brand.paper },
                  },
                },
              }}
            >
              <ToggleButton
                value="candidate"
                role="radio"
                aria-checked={role === 'candidate'}
                aria-label="Sign up as a candidate"
              >
                Candidate
              </ToggleButton>
              <ToggleButton
                value="employer"
                role="radio"
                aria-checked={role === 'employer'}
                aria-label="Sign up as an employer"
              >
                Employer
              </ToggleButton>
            </ToggleButtonGroup>
            <Typography variant="caption" color="text.secondary" sx={{ px: 0.5 }}>
              {role === 'employer'
                ? 'Post roles and review applicants.'
                : 'Build a profile and apply with your CV.'}
            </Typography>
          </Stack>
          <FormTextField<RegisterValues>
            name="name"
            control={control}
            label="Full name"
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <PersonOutlineRounded fontSize="small" />
                </InputAdornment>
              ),
            }}
          />
          {role === 'employer' ? (
            <FormTextField<RegisterValues>
              name="companyName"
              control={control}
              label="Company name"
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <BusinessOutlined fontSize="small" />
                  </InputAdornment>
                ),
              }}
            />
          ) : (
            <FormTextField<RegisterValues>
              name="headline"
              control={control}
              label="Headline (optional)"
              placeholder="e.g. Backend engineer"
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <WorkOutlineRounded fontSize="small" />
                  </InputAdornment>
                ),
              }}
            />
          )}
          <FormTextField<RegisterValues>
            name="email"
            control={control}
            label="Email"
            type="email"
            autoComplete="email"
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <EmailOutlined fontSize="small" />
                </InputAdornment>
              ),
            }}
          />
          <FormTextField<RegisterValues>
            name="password"
            control={control}
            label="Password"
            type={showPassword ? 'text' : 'password'}
            autoComplete="new-password"
            helperText="At least 8 characters"
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <LockOutlined fontSize="small" />
                </InputAdornment>
              ),
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton
                    onClick={() => setShowPassword((value) => !value)}
                    edge="end"
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                  >
                    {showPassword ? <VisibilityOffOutlined /> : <VisibilityOutlined />}
                  </IconButton>
                </InputAdornment>
              ),
            }}
          />
          <Button
            type="submit"
            variant="contained"
            disabled={isSubmitting}
            fullWidth
            size="large"
            startIcon={isSubmitting ? <CircularProgress size={18} color="inherit" /> : undefined}
          >
            {isSubmitting ? 'Creating account…' : 'Create account'}
          </Button>
        </Stack>
      </form>
    </AuthLayout>
  )
}