import request from './request'

export const depsApi = {
  list(type: string) {
    return request.get('/deps', { params: { type } }) as Promise<{ data: any[]; total: number }>
  },

  create(type: string, names: string[]) {
    return request.post('/deps', { type, names }) as Promise<{ message: string; data: any[] }>
  },

  delete(id: number, force?: boolean) {
    return request.delete(`/deps/${id}`, { params: force ? { force: true } : undefined }) as Promise<{ message: string }>
  },

  batchDelete(ids: number[]) {
    return request.post('/deps/batch-delete', { ids }) as Promise<{ message: string }>
  },

  getStatus(id: number) {
    return request.get(`/deps/${id}/status`) as Promise<{ data: any }>
  },

  reinstall(id: number) {
    return request.put(`/deps/${id}/reinstall`) as Promise<{ message: string }>
  },

  pipList: () => request.get('/deps/pip'),
  npmList: () => request.get('/deps/npm'),

  getMirrors() {
    return request.get('/deps/mirrors') as Promise<{ pip_mirror: string; npm_mirror: string; linux_mirror: string }>
  },

  setMirrors(data: { pip_mirror?: string; npm_mirror?: string; linux_mirror?: string }) {
    return request.put('/deps/mirrors', data) as Promise<{ message: string }>
  },
}
