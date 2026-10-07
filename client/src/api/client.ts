import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { tokenStore } from '@/auth/tokenStore'
import type { ApiEnvelope, AuthSession } from '@/types/auth'

const baseURL = import.meta.env.VITE_API_BASE_URL ?? '/api'

const api = axios.create({ baseURL })

/**
 * Resolves an API-root-relative path (the shape the server emits, e.g.
 * `profile/employers/<id>/logo`) to something an `<img src>` can load.
 *
 * Exported because not every asset goes through axios: an image tag cannot send
 * an Authorization header, which is exactly why the logo route is public. The
 * path is relative on the wire so it stays correct whichever base URL this
 * deployment is configured with.
 */
export function apiAssetUrl(path: string): string {
  return `${baseURL.replace(/\/$/, '')}/${path.replace(/^\//, '')}`
}

const refreshClient = axios.create({
  baseURL,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const accessToken = tokenStore.getAccess()
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`
  }
  if (!(config.data instanceof FormData) && config.headers.get('Content-Type') === null) {
    config.headers.set('Content-Type', 'application/json')
  }
  return config
})

let refreshInFlight: Promise<string> | null = null

async function refreshAccessToken(): Promise<string> {
  const refreshToken = tokenStore.getRefresh()
  if (!refreshToken) {
    throw new Error('No refresh token available')
  }
  const { data } = await refreshClient.post<ApiEnvelope<AuthSession>>('/auth/refresh', {
    refreshToken,
  })
  tokenStore.set(data.data.accessToken, data.data.refreshToken)
  return data.data.accessToken
}

function redirectToLogin(): void {
  tokenStore.clear()
  if (window.location.pathname !== '/login') {
    window.location.href = '/login'
  }
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined
    const status = error.response?.status
    const url = original?.url ?? ''
    const isAuthEndpoint = url.includes('/auth/login') || url.includes('/auth/refresh')

    if (status === 401 && original && !original._retry && !isAuthEndpoint) {
      original._retry = true
      try {
        refreshInFlight = refreshInFlight ?? refreshAccessToken()
        const accessToken = await refreshInFlight
        refreshInFlight = null
        original.headers.Authorization = `Bearer ${accessToken}`
        return api(original)
      } catch {
        refreshInFlight = null
        redirectToLogin()
      }
    }

    return Promise.reject(error)
  },
)

export default api