import { EmailOutlined, LockOutlined, VisibilityOffOutlined, VisibilityOutlined } from '@mui/icons-material'
import {
  Alert,
  Button,
  CircularProgress,
  IconButton,
  InputAdornment,
  Link,
  Stack,
  Typography,
} from '@mui/material'
import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect, useRef, useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link as RouterLink, useLocation, useNavigate } from 'react-router-dom'
import { getErrorDetails, getErrorMessage } from '@/api/errors'
import { useAuth } from '@/auth/AuthContext'
import { DASHBOARD_PATH } from '@/auth/RequireAuth'
import AuthLayout from '@/components/auth/AuthLayout'
import { FormTextField } from '@/components/shared/forms'
import { loginSchema, type LoginValues } from '@/schemas/auth'

const FIELDS = ['email', 'password'] as const

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from

  const [showPassword, setShowPassword] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const alertRef = useRef<HTMLDivElement>(null)
  const {
    control,
    handleSubmit,
    setError,
    clearErrors,
    watch,
    formState: { isSubmitting },
  } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: '', password: '' },
  })

  useEffect(() => {
    const subscription = watch(() => setSubmitError(null))
    return () => subscription.unsubscribe()
  }, [watch])

  useEffect(() => {
    if (submitError) alertRef.current?.focus()
  }, [submitError])

  async function onSubmit(values: LoginValues) {
    setSubmitError(null)
    clearErrors([...FIELDS])
    try {
      await login(values.email, values.password)
      navigate(from ?? DASHBOARD_PATH, { replace: true })
    } catch (err) {
      for (const detail of getErrorDetails(err)) {
        if (FIELDS.includes(detail.field as (typeof FIELDS)[number])) {
          setError(detail.field as 'email' | 'password', { type: 'server', message: detail.message })
        }
      }
      setSubmitError(getErrorMessage(err))
    }
  }

  return (
    <AuthLayout
      title="Welcome back"
      subtitle="Log in to continue to your dashboard."
      footer={
        <Typography variant="body2" color="text.secondary">
          New here?{' '}
          <Link component={RouterLink} to="/register">
            Create an account
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
          <FormTextField<LoginValues>
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
          <FormTextField<LoginValues>
            name="password"
            control={control}
            label="Password"
            type={showPassword ? 'text' : 'password'}
            autoComplete="current-password"
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
            {isSubmitting ? 'Logging in…' : 'Log in'}
          </Button>
        </Stack>
      </form>
    </AuthLayout>
  )
}
