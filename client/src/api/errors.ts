import axios from 'axios'
import type { ApiErrorDetail, ApiErrorEnvelope } from '@/types/auth'

function envelope(error: unknown): ApiErrorEnvelope | undefined {
  if (!axios.isAxiosError(error)) return undefined
  return error.response?.data as ApiErrorEnvelope | undefined
}

/**
 * Top-level human-readable message for an API failure.
 *
 * Prefers the server's `error.message`, but falls back to the first field-level
 * detail when the server returns only a generic summary (Marshmallow's
 * "Request validation failed"). Without that fallback a 422 surfaces as a dead
 * end: the user is told the request failed and nothing about which field.
 */
export function getErrorMessage(error: unknown): string {
  const data = envelope(error)
  if (data?.error) {
    if (data.error.message && data.error.message !== 'Request validation failed') {
      return data.error.message
    }
    const first = data.error.details?.[0]?.message
    if (first) return first
    if (data.error.message) return data.error.message
  }
  if (axios.isAxiosError(error)) {
    if (!error.response) return 'Cannot reach the server. Check your connection and try again.'
    return error.message
  }
  if (error instanceof Error) {
    return error.message
  }
  return 'Something went wrong'
}

/**
 * Field-level validation details from a 422, shaped for RHF's `setError`.
 *
 * `validation_error` is the only code whose `details[]` are addressable to
 * inputs; other codes (duplicate email, invalid credentials) are whole-form
 * problems and return an empty list so callers keep showing them in the alert.
 */
export function getErrorDetails(error: unknown): ApiErrorDetail[] {
  const data = envelope(error)
  if (data?.error?.code !== 'validation_error') return []
  return (data.error.details ?? []).filter((d) => typeof d.field === 'string' && !!d.field)
}
