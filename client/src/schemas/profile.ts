import { z } from 'zod'

export const COMPANY_SIZES = ['1-10', '11-50', '51-200', '201-500', '501-1000', '1000+'] as const

/** Mirrors ``MAX_LOGO_BYTES`` in ``server/app/services/logo_service.py``. */
export const LOGO_SIZE_LIMIT_BYTES = 1 * 1024 * 1024

/**
 * The formats ``logo_service.validate_logo`` accepts. The server is
 * authoritative; these mirror it so the user is told the real rule before the
 * upload instead of getting a 422 after it.
 *
 * SVG is accepted here (unlike an avatar) because real logos are often vector
 * artwork, and the logo serving route neutralises a script vector with a
 * ``default-src 'none'; sandbox`` CSP.
 */
export const LOGO_MIME_TYPES = ['image/png', 'image/jpeg', 'image/webp', 'image/svg+xml']

export const LOGO_ACCEPT = {
  types: LOGO_MIME_TYPES,
  maxSize: LOGO_SIZE_LIMIT_BYTES,
}

/**
 * Mirrors ``MAX_AVATAR_BYTES`` in ``server/app/services/avatar_service.py``.
 *
 * The Dropzone's own ``accept`` prop is the validator for both this and the logo:
 * both upload the moment a file is chosen, not on save, so neither belongs in
 * ``employerProfileSchema``. Keeping the rules in one exported config is what
 * stops the page and the API disagreeing about them.
 */
export const AVATAR_SIZE_LIMIT_BYTES = 1 * 1024 * 1024

/** Raster only — the server refuses SVG for an avatar, with a real CSP, not a fake one. */
export const AVATAR_MIME_TYPES = ['image/png', 'image/jpeg', 'image/webp']

export const AVATAR_ACCEPT = {
  types: AVATAR_MIME_TYPES,
  maxSize: AVATAR_SIZE_LIMIT_BYTES,
}

const textSchema = (label: string, max: number) =>
  z
    .string({ required_error: `${label} is required` })
    .trim()
    .min(1, `${label} is required`)
    .max(max, `${label} must be at most ${max} characters`)

export const employerProfileSchema = z.object({
  name: textSchema('Your name', 120),
  companyName: textSchema('Company name', 120),
  companySize: z.enum(COMPANY_SIZES, {
    required_error: 'Company size is required',
  }),
  companyIndustry: textSchema('Industry', 120),
  companyDescription: z
    .string({ required_error: 'Company description is required' })
    .trim()
    .min(1, 'Company description is required')
    .max(2000, 'Company description must be at most 2000 characters'),
})

export type EmployerProfileValues = z.infer<typeof employerProfileSchema>

/** Defaults for a profile that has never been saved. */
export function emptyEmployerProfile(): EmployerProfileValues {
  return {
    name: '',
    companyName: '',
    companySize: '11-50',
    companyIndustry: '',
    companyDescription: '',
  }
}
