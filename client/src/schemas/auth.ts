import { z } from 'zod'

/**
 * Client mirror of `server/app/schemas/user.py`. The numbers are duplicated
 * deliberately: the API boundary is the only place shape is enforced, and these
 * are the exact limits `UserCreateSchema` enforces, so the form can reject a
 * value before spending a round trip on a 422.
 */
const PASSWORD_MIN = 8
const PASSWORD_MAX_BYTES = 72
const MAX_NAME_LEN = 120
const MAX_HEADLINE_LEN = 160

const encoder = new TextEncoder()
const byteLength = (value: string) => encoder.encode(value).length

/**
 * The server stores emails trimmed and lowercased (`UserCreateSchema._validate`,
 * `AuthService.authenticate`). Validating the raw string meant a value with
 * stray whitespace or capitals passed the API and was rejected by it, so the
 * same normalization is applied before the regex sees it.
 */
const emailSchema = z
  .string({ required_error: 'Email is required' })
  .trim()
  .toLowerCase()
  .min(1, 'Email is required')
  .regex(/^[^@\s]+@[^@\s]+\.[^@\s]+$/, 'Email is not valid')

/**
 * Login deliberately has no length policy. `/api/auth/login` runs no schema —
 * it hands the credentials straight to `AuthService.authenticate` — so a
 * "must be at least 8 characters" message on a login form is a client-side
 * invention that hides the real failure (wrong credentials) behind a comment
 * about a rule the endpoint does not have.
 */
const loginPasswordSchema = z
  .string({ required_error: 'Password is required' })
  .min(1, 'Password is required')

const registerPasswordSchema = loginPasswordSchema
  .min(PASSWORD_MIN, `Password must be at least ${PASSWORD_MIN} characters`)
  .refine((value) => byteLength(value) <= PASSWORD_MAX_BYTES, `Password must be at most ${PASSWORD_MAX_BYTES} bytes`)

const nameSchema = z
  .string({ required_error: 'Name is required' })
  .trim()
  .min(1, 'Name is required')
  .max(MAX_NAME_LEN, `Name must be at most ${MAX_NAME_LEN} characters`)

export const loginSchema = z.object({
  email: emailSchema,
  password: loginPasswordSchema,
})

export const registerSchema = z
  .object({
    role: z.enum(['employer', 'candidate'] as const, {
      required_error: 'Account type is required',
    }),
    name: nameSchema,
    companyName: z.string().trim().optional(),
    headline: z
      .string()
      .trim()
      .max(MAX_HEADLINE_LEN, `Headline must be at most ${MAX_HEADLINE_LEN} characters`)
      .optional(),
    email: emailSchema,
    password: registerPasswordSchema,
  })
  .superRefine((data, ctx) => {
    if (data.role === 'employer' && !data.companyName) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['companyName'],
        message: 'Company name is required',
      })
    }
  })

export type LoginValues = z.infer<typeof loginSchema>
export type RegisterValues = z.infer<typeof registerSchema>
