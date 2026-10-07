import { z } from 'zod'
import { CV_SIZE_LIMIT_BYTES } from '@/types/application'

const isAcceptedType = (file: File): boolean =>
  file.type === 'application/pdf' ||
  file.name.toLowerCase().endsWith('.pdf') ||
  file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' ||
  file.name.toLowerCase().endsWith('.docx')

export const applyFormSchema = z.object({
  cv: z
    .custom<File>()
    .refine((file) => file instanceof File && file.size > 0, { message: 'Choose a CV to apply with.' })
    .refine((file) => file instanceof File && isAcceptedType(file), {
      message: 'CV must be a PDF or DOCX file.',
    })
    .refine((file) => file instanceof File && file.size <= CV_SIZE_LIMIT_BYTES, {
      message: 'CV must be under 5MB.',
    })
    .optional(),
})

export const applyFormSchemaWithProfileCv = z.object({
  cv: z
    .custom<File>()
    .refine((file) => file instanceof File && file.size > 0, { message: 'Choose a CV to apply with.' })
    .refine((file) => file instanceof File && isAcceptedType(file), {
      message: 'CV must be a PDF or DOCX file.',
    })
    .refine((file) => file instanceof File && file.size <= CV_SIZE_LIMIT_BYTES, {
      message: 'CV must be under 5MB.',
    })
    .optional(),
  useProfileCv: z.boolean().optional(),
}).refine((data) => data.cv || data.useProfileCv, {
  message: 'Choose a CV to apply with.',
  path: ['cv'],
})

export type ApplyFormValues = z.infer<typeof applyFormSchema>
export type ApplyFormValuesWithProfile = z.infer<typeof applyFormSchemaWithProfileCv>