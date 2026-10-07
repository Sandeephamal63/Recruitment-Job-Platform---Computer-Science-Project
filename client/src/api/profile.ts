import api from '@/api/client'
import type { ApiEnvelope } from '@/types/auth'
import type {
  User,
  ProfileAvatarUploadResponse,
  ProfileCvUploadResponse,
  ProfileLogoUploadResponse,
} from '@/types/profile'

export async function getProfile(): Promise<User> {
  const { data } = await api.get<ApiEnvelope<User>>('/profile/me')
  return data.data
}

export async function updateProfile(updates: Partial<User>): Promise<User> {
  const { data } = await api.patch<ApiEnvelope<User>>('/profile/me', updates)
  return data.data
}

export async function uploadProfileCv(file: File): Promise<ProfileCvUploadResponse> {
  const form = new FormData()
  form.append('cv', file)
  const { data } = await api.post<ApiEnvelope<ProfileCvUploadResponse>>('/profile/me/cv', form)
  return data.data
}

export async function downloadProfileCv(): Promise<Blob> {
  const { data } = await api.get<Blob>('/profile/me/cv', { responseType: 'blob' })
  return data
}

export async function deleteProfileCv(): Promise<User> {
  const { data } = await api.delete<ApiEnvelope<User>>('/profile/me/cv')
  return data.data
}

export async function uploadCompanyLogo(file: File): Promise<ProfileLogoUploadResponse> {
  const form = new FormData()
  form.append('logo', file)
  const { data } = await api.post<ApiEnvelope<ProfileLogoUploadResponse>>('/profile/me/logo', form)
  return data.data
}

export async function deleteCompanyLogo(): Promise<User> {
  const { data } = await api.delete<ApiEnvelope<User>>('/profile/me/logo')
  return data.data
}

export async function uploadAvatar(file: File): Promise<ProfileAvatarUploadResponse> {
  const form = new FormData()
  form.append('avatar', file)
  const { data } = await api.post<ApiEnvelope<ProfileAvatarUploadResponse>>('/profile/me/avatar', form)
  return data.data
}

/**
 * The signed-in candidate's own avatar, as raw image bytes.
 *
 * Unlike a company logo there is no public avatar URL to hand an `<img>`, so the
 * bytes come through the API (which attaches the bearer token) and the caller
 * wraps them in an object URL.
 */
export async function fetchOwnAvatar(): Promise<Blob> {
  const { data } = await api.get<Blob>('/profile/me/avatar', { responseType: 'blob' })
  return data
}

/**
 * An applicant's avatar for the employer who owns the job they applied to.
 *
 * Keyed on the application, not the candidate: the API rejects an employer who
 * does not own the job, and a URL built from a candidate id would invite exactly
 * that mistake at the call site.
 */
export async function fetchCandidateAvatar(applicationId: string): Promise<Blob> {
  const { data } = await api.get<Blob>(
    `/profile/applications/${applicationId}/candidate-avatar`,
    { responseType: 'blob' },
  )
  return data
}

export async function deleteAvatar(): Promise<User> {
  const { data } = await api.delete<ApiEnvelope<User>>('/profile/me/avatar')
  return data.data
}