import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器：自动附加 JWT Token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error),
)

// Token 刷新状态
let isRefreshing = false
let failedQueue: Array<{ resolve: (value?: any) => void; reject: (reason?: any) => void }> = []

const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error)
    } else {
      prom.resolve(token)
    }
  })
  failedQueue = []
}

// 响应拦截器：处理 401 并自动刷新 Token
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    // 如果是 401 错误且不是刷新 Token 的请求
    if (error.response?.status === 401 && !originalRequest._retry) {
      if (originalRequest.url === '/auth/refresh') {
        // 刷新 Token 失败，清理并跳转登录
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        if (window.location.pathname !== '/login') {
          window.location.href = '/login'
        }
        return Promise.reject(error)
      }

      if (isRefreshing) {
        // 如果正在刷新，将请求加入队列
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        })
          .then((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`
            return api(originalRequest)
          })
          .catch((err) => Promise.reject(err))
      }

      originalRequest._retry = true
      isRefreshing = true

      const refreshToken = localStorage.getItem('refresh_token')
      if (!refreshToken) {
        // 没有 refresh token，直接跳转登录
        localStorage.removeItem('access_token')
        if (window.location.pathname !== '/login') {
          window.location.href = '/login'
        }
        return Promise.reject(error)
      }

      try {
        // 尝试刷新 Token
        const response = await api.post(
          '/auth/refresh',
          {},
          {
            headers: { Authorization: `Bearer ${refreshToken}` },
          }
        )
        const { access_token } = response.data
        localStorage.setItem('access_token', access_token)

        // 更新原请求的 Token
        originalRequest.headers.Authorization = `Bearer ${access_token}`

        // 处理队列中的请求
        processQueue(null, access_token)

        isRefreshing = false

        // 重试原请求
        return api(originalRequest)
      } catch (refreshError) {
        // 刷新失败，清理并跳转登录
        processQueue(refreshError, null)
        isRefreshing = false

        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        if (window.location.pathname !== '/login') {
          window.location.href = '/login'
        }
        return Promise.reject(refreshError)
      }
    }

    return Promise.reject(error)
  },
)

// ==================== 认证接口 ====================

export const authApi = {
  init: (data: { username: string; password: string }) =>
    api.post('/auth/init', data),

  login: (data: {
    username: string; password: string; totp_token?: string;
    lot_number?: string; captcha_output?: string; pass_token?: string; gen_time?: string
  }) =>
    api.post('/auth/login', data),

  getUser: () =>
    api.get('/auth/user'),

  changePassword: (data: { old_password: string; new_password: string }) =>
    api.put('/auth/password', data),

  logout: () =>
    api.post('/auth/logout'),

  refresh: () =>
    api.post('/auth/refresh', {}, {
      headers: { Authorization: `Bearer ${localStorage.getItem('refresh_token')}` },
    }),
}

// ==================== 任务接口 ====================

export interface TaskParams {
  keyword?: string
  status?: number
  label?: string
  page?: number
  page_size?: number
}

export interface TaskData {
  name: string
  command: string
  cron_expression: string
  timeout?: number
  max_retries?: number
  retry_interval?: number
  notify_on_failure?: boolean
  depends_on?: number | null
  labels?: string[]
}

export const taskApi = {
  list: (params?: TaskParams) =>
    api.get('/tasks', { params }),

  create: (data: TaskData) =>
    api.post('/tasks', data),

  update: (id: number, data: Partial<TaskData>) =>
    api.put(`/tasks/${id}`, data),

  delete: (id: number) =>
    api.delete(`/tasks/${id}`),

  run: (id: number) =>
    api.put(`/tasks/${id}/run`),

  stop: (id: number) =>
    api.put(`/tasks/${id}/stop`),

  enable: (id: number) =>
    api.put(`/tasks/${id}/enable`),

  disable: (id: number) =>
    api.put(`/tasks/${id}/disable`),

  batch: (ids: number[], action: string) =>
    api.put('/tasks/batch', { ids, action }),

  getLiveLogs: (id: number) =>
    api.get(`/tasks/${id}/live-logs`),

  getLatestLog: (id: number) =>
    api.get(`/tasks/${id}/latest-log`),

  pin: (id: number) =>
    api.put(`/tasks/${id}/pin`),

  unpin: (id: number) =>
    api.put(`/tasks/${id}/unpin`),

  copy: (id: number) =>
    api.post(`/tasks/${id}/copy`),

  listLogFiles: (id: number) =>
    api.get(`/tasks/${id}/log-files`),

  getLogFileContent: (id: number, filename: string) =>
    api.get(`/tasks/${id}/log-files/${filename}`),

  deleteLogFile: (id: number, filename: string) =>
    api.delete(`/tasks/${id}/log-files/${filename}`),

  downloadLogFile: (id: number, filename: string) =>
    `/api/tasks/${id}/log-files/${filename}/download`,

  cleanOldLogs: (days: number = 7) =>
    api.delete('/tasks/clean-logs', { params: { days } }),

  exportTasks: () =>
    api.get('/tasks/export'),

  importTasks: (tasks: any[]) =>
    api.post('/tasks/import', { tasks }),
}

// ==================== 日志接口 ====================

export interface LogParams {
  task_id?: number
  status?: number
  keyword?: string
  page?: number
  page_size?: number
}

export const logApi = {
  list: (params?: LogParams) =>
    api.get('/logs', { params }),

  get: (id: number) =>
    api.get(`/logs/${id}`),

  delete: (id: number) =>
    api.delete(`/logs/${id}`),

  clean: (days?: number) =>
    api.delete('/logs/clean', { params: { days } }),
}

// ==================== 脚本管理接口 ====================

export const scriptApi = {
  list: () =>
    api.get('/scripts'),

  tree: () =>
    api.get('/scripts/tree'),

  getContent: (path: string) =>
    api.get('/scripts/content', { params: { path } }),

  saveContent: (data: { path: string; content: string; message?: string }) =>
    api.put('/scripts/content', data),

  upload: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/scripts/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  delete: (path: string) =>
    api.delete('/scripts', { params: { path } }),

  listVersions: (path: string) =>
    api.get('/scripts/versions', { params: { path } }),

  getVersion: (versionId: number) =>
    api.get(`/scripts/versions/${versionId}`),

  rollback: (versionId: number) =>
    api.put(`/scripts/versions/${versionId}/rollback`),

  // 调试运行
  run: (path: string) =>
    api.post('/scripts/run', { path }),

  getLogs: (runId: string) =>
    api.get(`/scripts/run/${runId}/logs`),

  stopRun: (runId: string) =>
    api.put(`/scripts/run/${runId}/stop`),

  clearRun: (runId: string) =>
    api.delete(`/scripts/run/${runId}`),

  // 代码格式化
  format: (data: { content: string; language: string; formatter?: string }) =>
    api.post('/scripts/format', data),

  // 文件夹管理
  createDirectory: (path: string) =>
    api.post('/scripts/directory', { path }),
}

// ==================== 环境变量接口 ====================

export interface EnvParams {
  keyword?: string
  group?: string
  page?: number
  page_size?: number
}

export const envApi = {
  list: (params?: EnvParams) =>
    api.get('/envs', { params }),

  create: (data: { name: string; value: string; remarks?: string; group?: string }) =>
    api.post('/envs', data),

  update: (id: number, data: { name?: string; value?: string; remarks?: string; group?: string }) =>
    api.put(`/envs/${id}`, data),

  delete: (id: number) =>
    api.delete(`/envs/${id}`),

  enable: (id: number) =>
    api.put(`/envs/${id}/enable`),

  disable: (id: number) =>
    api.put(`/envs/${id}/disable`),

  batchDelete: (ids: number[]) =>
    api.delete('/envs/batch', { data: { ids } }),

  updateSort: (ids: number[]) =>
    api.put('/envs/sort', { ids }),

  listGroups: () =>
    api.get('/envs/groups'),

  exportAll: () =>
    api.get('/envs/export-all'),

  import: (envs: any[], mode: 'merge' | 'replace' = 'merge') =>
    api.post('/envs/import', { envs, mode }),
}

// ==================== 开放 API 接口 ====================

export const openApiApi = {
  listApps: () =>
    api.get('/open/apps'),

  createApp: (data: { name: string; scopes?: string[]; token_expiry?: number }) =>
    api.post('/open/apps', data),

  updateApp: (id: number, data: { name?: string; scopes?: string[]; token_expiry?: number; enabled?: boolean }) =>
    api.put(`/open/apps/${id}`, data),

  deleteApp: (id: number) =>
    api.delete(`/open/apps/${id}`),

  resetSecret: (id: number) =>
    api.put(`/open/apps/${id}/reset-secret`),

  getSecret: (id: number, password: string) =>
    api.post(`/open/apps/${id}/secret`, { password }),

  getCallLogs: (appId: number, params?: { page?: number; page_size?: number }) =>
    api.get(`/open/apps/${appId}/logs`, { params }),
}

// ==================== 系统信息接口 ====================

export const systemApi = {
  getInfo: () =>
    api.get('/system/info'),

  getStats: () =>
    api.get('/system/stats'),

  getTrend: () =>
    api.get('/system/stats/trend'),

  getDurationStats: () =>
    api.get('/system/stats/duration'),

  getSuccessRateStats: () =>
    api.get('/system/stats/task-success-rate'),

  createBackup: (password: string) =>
    api.post('/system/backup', { password }),

  listBackups: () =>
    api.get('/system/backup/list'),

  deleteBackup: (filename: string) =>
    api.delete(`/system/backup/${filename}`),

  restore: (filename: string, password?: string) =>
    api.post('/system/restore', { filename, password }),

  panelLog: (params?: { lines?: number; keyword?: string }) =>
    api.get('/system/panel-log', { params }),

  getVersion: () =>
    api.get('/system/version'),

  checkUpdate: () =>
    api.get('/system/check-update'),
}

// ==================== 订阅管理接口 ====================

export const subApi = {
  list: () =>
    api.get('/subscriptions'),

  create: (data: { name: string; url: string; branch?: string; schedule?: string; whitelist?: string; blacklist?: string; target_dir?: string }) =>
    api.post('/subscriptions', data),

  update: (id: number, data: Record<string, any>) =>
    api.put(`/subscriptions/${id}`, data),

  delete: (id: number) =>
    api.delete(`/subscriptions/${id}`),

  pull: (id: number) =>
    api.post(`/subscriptions/${id}/pull`),

  logs: (params?: { sub_id?: number; page?: number; page_size?: number }) =>
    api.get('/subscriptions/logs', { params }),
}

// ==================== 通知渠道接口 ====================

export const notifyApi = {
  list: () =>
    api.get('/notifications'),

  create: (data: { name: string; type: string; config: Record<string, any> }) =>
    api.post('/notifications', data),

  update: (id: number, data: Record<string, any>) =>
    api.put(`/notifications/${id}`, data),

  delete: (id: number) =>
    api.delete(`/notifications/${id}`),

  test: (id: number) =>
    api.post(`/notifications/${id}/test`),
}

// ==================== 依赖管理接口 ====================

export const depsApi = {
  listPython: () =>
    api.get('/deps/python'),

  installPython: (name: string) =>
    api.post('/deps/python', { name }),

  batchInstallPython: (names: string[]) =>
    api.post('/deps/python', { names }),

  uninstallPython: (name: string) =>
    api.delete('/deps/python', { params: { name } }),

  listNode: () =>
    api.get('/deps/node'),

  installNode: (name: string) =>
    api.post('/deps/node', { name }),

  uninstallNode: (name: string) =>
    api.delete('/deps/node', { params: { name } }),
}

// ==================== 用户管理接口 ====================

export const userApi = {
  list: () =>
    api.get('/users'),

  create: (data: { username: string; password: string; role: string }) =>
    api.post('/users', data),

  update: (id: number, data: Record<string, any>) =>
    api.put(`/users/${id}`, data),

  delete: (id: number) =>
    api.delete(`/users/${id}`),
}

// ==================== 系统配置接口 ====================

export const configApi = {
  getAll: () =>
    api.get('/config'),

  update: (configs: Record<string, string>) =>
    api.put('/config', { configs }),
}

// ==================== 双因素认证接口 ====================

export const twoFactorApi = {
  // 获取2FA状态
  getStatus: () =>
    api.get('/security/2fa/status'),

  // 设置2FA（获取密钥和二维码）
  setup: () =>
    api.post('/security/2fa/setup'),

  // 启用2FA
  enable: (token: string) =>
    api.post('/security/2fa/enable', { token }),

  // 禁用2FA
  disable: (password: string) =>
    api.post('/security/2fa/disable', { password }),

  // 重新生成备用码
  regenerateBackupCodes: (password: string) =>
    api.post('/security/2fa/regenerate-backup-codes', { password }),
}

// ==================== 安全管理接口 ====================

export const securityApi = {
  // 登录日志
  listLoginLogs: (params?: { user_id?: number; status?: number; page?: number; page_size?: number }) =>
    api.get('/security/login-logs', { params }),

  cleanLoginLogs: (days: number = 90) =>
    api.delete('/security/login-logs/clean', { params: { days } }),

  // 会话管理
  listSessions: () =>
    api.get('/security/sessions'),

  revokeSession: (sessionId: number) =>
    api.delete(`/security/sessions/${sessionId}`),

  revokeAllSessions: () =>
    api.post('/security/sessions/revoke-all'),

  // IP白名单
  listIPWhitelist: () =>
    api.get('/security/ip-whitelist'),

  addIPWhitelist: (data: { ip_address: string; description?: string }) =>
    api.post('/security/ip-whitelist', data),

  updateIPWhitelist: (id: number, data: { description?: string; enabled?: boolean }) =>
    api.put(`/security/ip-whitelist/${id}`, data),

  deleteIPWhitelist: (id: number) =>
    api.delete(`/security/ip-whitelist/${id}`),
}

export default api
