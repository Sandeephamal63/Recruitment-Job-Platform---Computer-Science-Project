import { z } from 'zod'
import { EMPLOYMENT_TYPES, type Job, type JobPayload } from '@/types/jobs'
import { todayAsInputValue } from '@/utils/dates'

const textSchema = (label: string, max: number) =>
  z
    .string({ required_error: `${label} is required` })
    .trim()
    .min(1, `${label} is required`)
    .max(max, `${label} must be at most ${max} characters`)

/**
 * A bare `YYYY-MM-DD`, or `''` for "no deadline".
 *
 * The server stores a deadline as the end of the day it names, so today is
 * always allowed — only earlier dates are rejected. This mirrors that check so
 * the employer finds out before submitting, but the server's validation is the
 * one that counts; a client clock can be wrong and the 422 is authoritative.
 */
const deadlineSchema = z
  .string()
  .refine((value) => value === '' || /^\d{4}-\d{2}-\d{2}$/.test(value), {
    message: 'Deadline must be a date',
  })
  .refine((value) => value === '' || value >= todayAsInputValue(), {
    message: 'Deadline cannot be in the past',
  })

export const jobFormSchema = z.object({
  title: textSchema('Title', 120),
  description: z
    .string({ required_error: 'Description is required' })
    .trim()
    .min(1, 'Description is required'),
  location: textSchema('Location', 120),
  employmentType: z.enum(EMPLOYMENT_TYPES, {
    required_error: 'Employment type is required',
  }),
  requiredSkills: z.array(z.string()),
  deadline: deadlineSchema,
})

export type JobFormValues = z.infer<typeof jobFormSchema>

export function parseSkills(input: string): string[] {
  return input
    .split(',')
    .map((skill) => skill.trim())
    .filter(Boolean)
}

export function toJobPayload(values: JobFormValues): JobPayload {
  // An empty date input means "no deadline", which the API expresses as an
  // absent field — sending `''` would be a date the server cannot parse.
  const { deadline, ...rest } = values
  return deadline ? { ...rest, deadline } : rest
}

export function toJobFormValues(job: Job): JobFormValues {
  return {
    title: job.title,
    description: job.description,
    location: job.location,
    employmentType: job.employmentType as 'full-time' | 'part-time' | 'contract',
    requiredSkills: job.requiredSkills,
    deadline: job.deadline ?? '',
  }
}