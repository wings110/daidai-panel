import { create } from 'zustand'
import { authApi } from '../services/api'

interface User {
  id: number
  username: string
  role: string
}

interface CaptchaData {
  lot_number: string
  captcha_output: string
  pass_token: string
  gen_time: string
}

interface AuthState {
  user: User | null
  isLoggedIn: boolean
  needInit: boolean
  loading: boolean
  login: (username: string, password: string, totp_token?: string, captcha?: CaptchaData) => Promise<void>
  initAdmin: (username: string, password: string) => Promise<void>
  logout: () => void
  fetchUser: () => Promise<void>
  checkAuth: () => Promise<boolean>
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isLoggedIn: false, // 初始状态为未登录，由 App.tsx 中的 checkAuth 来验证
  needInit: false,
  loading: false,

  login: async (username: string, password: string, totp_token?: string, captcha?: CaptchaData) => {
    const res = await authApi.login({ username, password, totp_token, ...captcha })
    const { access_token, refresh_token, user } = res.data
    localStorage.setItem('access_token', access_token)
    localStorage.setItem('refresh_token', refresh_token)
    set({ user, isLoggedIn: true, needInit: false })
  },

  initAdmin: async (username: string, password: string) => {
    await authApi.init({ username, password })
    set({ needInit: false })
  },

  logout: async () => {
    try {
      await authApi.logout()
    } catch {
      // Token 可能已过期，忽略错误
    }
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    set({ user: null, isLoggedIn: false })
    window.location.href = '/login'
  },

  fetchUser: async () => {
    try {
      const res = await authApi.getUser()
      set({ user: res.data.user, isLoggedIn: true })
    } catch {
      set({ user: null, isLoggedIn: false })
    }
  },

  checkAuth: async () => {
    const token = localStorage.getItem('access_token')
    if (!token) {
      set({ isLoggedIn: false, user: null })
      return false
    }
    try {
      const res = await authApi.getUser()
      set({ user: res.data.user, isLoggedIn: true })
      return true
    } catch {
      // Token 无效，清理 localStorage
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      set({ isLoggedIn: false, user: null })
      return false
    }
  },
}))
