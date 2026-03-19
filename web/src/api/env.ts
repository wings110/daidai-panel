import request from './request'

export const envApi = {
  list(params?: { keyword?: string; group?: string; page?: number; page_size?: number }) {
    return request.get('/envs', { params }) as Promise<{ data: any[]; total: number; page: number; page_size: number }>
  },

  create(data: { name: string; value?: string; remarks?: string; group?: string } | { name: string; value?: string; remarks?: string; group?: string }[]) {
    return request.post('/envs', data) as Promise<{ message: string; data: any }>
  },

  update(id: number, data: any) {
    return request.put(`/envs/${id}`, data) as Promise<{ message: string; data: any }>
  },

  delete(id: number) {
    return request.delete(`/envs/${id}`) as Promise<{ message: string }>
  },

  enable(id: number) {
    return request.put(`/envs/${id}/enable`) as Promise<{ message: string; data: any }>
  },

  disable(id: number) {
    return request.put(`/envs/${id}/disable`) as Promise<{ message: string; data: any }>
  },

  batchDelete(ids: number[]) {
    return request.delete('/envs/batch', { data: { ids } }) as Promise<{ message: string }>
  },

  batchEnable(ids: number[]) {
    return request.put('/envs/batch/enable', { ids }) as Promise<{ message: string }>
  },

  batchDisable(ids: number[]) {
    return request.put('/envs/batch/disable', { ids }) as Promise<{ message: string }>
  },

  sort(sourceId: number, targetId?: number) {
    return request.put('/envs/sort', { source_id: sourceId, target_id: targetId }) as Promise<{ message: string }>
  },

  moveToTop(id: number) {
    return request.put(`/envs/${id}/move-top`) as Promise<{ message: string }>
  },

  groups() {
    return request.get('/envs/groups') as Promise<{ data: string[] }>
  },

  export() {
    return request.get('/envs/export') as Promise<{ data: Record<string, string> }>
  },

  exportAll() {
    return request.get('/envs/export-all') as Promise<{ data: any[] }>
  },

  exportFiles(format?: string, enabledOnly?: boolean) {
    return request.post('/envs/export-files', { format, enabled_only: enabledOnly }) as Promise<{ data: Record<string, string> }>
  },

  import(envs: any[], mode?: string) {
    return request.post('/envs/import', { envs, mode }) as Promise<{ message: string; errors: string[] }>
  }
}
