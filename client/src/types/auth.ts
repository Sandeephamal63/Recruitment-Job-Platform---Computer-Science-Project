export type Role = 'employer' | 'candidate'

export interface User {
  id: string
  role: Role
  name: string
  email: string
  createdAt: string
  companyName?: string
  headline?: string
  skills?: string[]
}

export interface AuthSession {
  accessToken: string
  refreshToken: string
  user: User
}

export interface RegisterPayload {
  role: Role
  name: string
  email: string
  password: string
  companyName?: string
  headline?: string
  skills?: string[]
}

export interface ApiErrorDetail {
  field: string
  message: string
}

export interface ApiError {
  code: string
  message: string
  details?: ApiErrorDetail[]
}

export interface PaginatedResponse {
  page: number
  pageSize: number
  total: number
  totalPages: number
  hasNext: boolean
  hasPrevious: boolean
}

export interface ApiEnvelope<T> {
  success: boolean
  data: T
  meta?: { pagination?: PaginatedResponse } & Record<string, unknown>
}

export interface ApiErrorEnvelope {
  success: false
  error: ApiError
}