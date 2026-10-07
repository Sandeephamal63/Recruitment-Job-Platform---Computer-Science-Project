export interface User {
  id: string
  role: 'employer' | 'candidate'
  name: string
  email: string
  createdAt: string
  updatedAt: string
  headline?: string
  skills?: string[]
  companyName?: string
  companyDescription?: string
  companyIndustry?: string
  companySize?: string
  /** API-root-relative path, or empty when the employer has uploaded no logo. */
  companyLogoUrl?: string | null
  companyLogoFileName?: string
  hasProfileCv: boolean
  cvFileName?: string
  cvParsedText?: string
  /** Stored filename of the candidate's avatar, or null when they have none. */
  avatarFileName?: string | null
  savedJobIds?: string[]
}

export interface SavedJob {
  id: string
  title: string
  location: string
  employmentType: string
  salaryMin: number | null
  salaryMax: number | null
  currency: string
  experienceLevel: string
  remote: boolean
  status: 'open' | 'closed'
  /** Last day applications are accepted, `YYYY-MM-DD`; `null` = open-ended. */
  deadline: string | null
  requiredSkills: string[]
  employer: EmployerSummary | null
}

export interface EmployerSummary {
  id: string
  name: string
  companyName: string
  companyDescription: string
  companyIndustry: string
  companySize: string
  companyLogoUrl: string | null
}

export interface ProfileCvUploadResponse {
  cvFileName: string
  extractedSkills: string[]
  characterCount: number
}

export interface ProfileLogoUploadResponse {
  companyLogoUrl: string
  companyLogoFileName: string
}

/**
 * No `avatarUrl`, unlike `ProfileLogoUploadResponse`. An avatar is only ever
 * read by an authenticated caller, so there is no address an `<img>` could load
 * — the client fetches the bytes and builds an object URL.
 */
export interface ProfileAvatarUploadResponse {
  avatarFileName: string
}