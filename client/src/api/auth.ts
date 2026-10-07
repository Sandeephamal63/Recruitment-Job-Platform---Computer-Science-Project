import api from '@/api/client'
import type { ApiEnvelope, AuthSession, RegisterPayload, User } from '@/types/auth'

export async function login(email: string, password: string): Promise<AuthSession> {
  const { data } = await api.post<ApiEnvelope<AuthSession>>('/auth/login', { email, password })
  return data.data
}

export async function register(payload: RegisterPayload): Promise<AuthSession> {
  const { data } = await api.post<ApiEnvelope<AuthSession>>('/auth/register', payload)
  return data.data
}

export async function me(): Promise<User> {
  const { data } = await api.get<ApiEnvelope<User>>('/auth/me')
  return data.data
}

export async function logout(refreshToken: string): Promise<void> {
  await api.post('/auth/logout', { refreshToken })
}