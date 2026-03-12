/**
 * API 文档数据定义
 * 每个接口包含：方法、路径、标题、描述、参数、响应示例
 */

export interface ApiParam {
  name: string
  type: string
  required?: boolean
  description: string
  example?: string
}

export interface ApiEndpoint {
  id: string
  method: 'GET' | 'POST' | 'PUT' | 'DELETE'
  path: string
  title: string
  description: string
  auth?: 'jwt' | 'open_api' | 'none'
  pathParams?: ApiParam[]
  queryParams?: ApiParam[]
  bodyParams?: ApiParam[]
  responseExample?: string
  responseFields?: ApiParam[]
}

export interface ApiCategory {
  key: string
  label: string
  endpoints: ApiEndpoint[]
}

export const API_BASE = '/api'

export const apiCategories: ApiCategory[] = [
  {
    key: 'auth',
    label: '认证',
    endpoints: [
      {
        id: 'auth-login',
        method: 'POST',
        path: '/api/auth/login',
        title: '用户登录',
        description: '使用用户名和密码登录，获取 JWT Token',
        auth: 'none',
        bodyParams: [
          { name: 'username', type: 'string', required: true, description: '用户名', example: 'admin' },
          { name: 'password', type: 'string', required: true, description: '密码', example: 'admin123' },
        ],
        responseExample: JSON.stringify({
          access_token: 'eyJhbGciOi...',
          refresh_token: 'eyJhbGciOi...',
          user: { id: 1, username: 'admin', role: 'admin' },
        }, null, 2),
        responseFields: [
          { name: 'access_token', type: 'string', description: 'JWT 访问令牌' },
          { name: 'refresh_token', type: 'string', description: 'JWT 刷新令牌' },
          { name: 'user', type: 'object', description: '用户信息' },
        ],
      },
      {
        id: 'auth-refresh',
        method: 'POST',
        path: '/api/auth/refresh',
        title: '刷新令牌',
        description: '使用 refresh_token 获取新的 access_token',
        auth: 'jwt',
        responseExample: JSON.stringify({ access_token: 'eyJhbGciOi...' }, null, 2),
      },
      {
        id: 'auth-me',
        method: 'GET',
        path: '/api/auth/me',
        title: '获取当前用户信息',
        description: '获取当前登录用户的详细信息',
        auth: 'jwt',
        responseExample: JSON.stringify({
          data: { id: 1, username: 'admin', role: 'admin', created_at: '2026-01-01T00:00:00' },
        }, null, 2),
      },
      {
        id: 'auth-password',
        method: 'PUT',
        path: '/api/auth/password',
        title: '修改密码',
        description: '修改当前用户密码',
        auth: 'jwt',
        bodyParams: [
          { name: 'old_password', type: 'string', required: true, description: '当前密码' },
          { name: 'new_password', type: 'string', required: true, description: '新密码（至少8位）' },
        ],
        responseExample: JSON.stringify({ message: '密码修改成功' }, null, 2),
      },
    ],
  },
  {
    key: 'tasks',
    label: '定时任务',
    endpoints: [
      {
        id: 'tasks-list',
        method: 'GET',
        path: '/api/tasks',
        title: '获取任务列表',
        description: '获取所有定时任务，支持关键字搜索和分页',
        auth: 'jwt',
        queryParams: [
          { name: 'keyword', type: 'string', description: '搜索关键字' },
          { name: 'page', type: 'integer', description: '页码，默认 1', example: '1' },
          { name: 'page_size', type: 'integer', description: '每页数量，默认 20', example: '20' },
        ],
        responseExample: JSON.stringify({
          data: [{
            id: 1, name: '签到任务', command: 'sign.py',
            schedule: '0 9 * * *', status: 1, last_run_status: 0,
            last_run_at: '2026-03-10T09:00:00',
          }],
          total: 1, page: 1, page_size: 20,
        }, null, 2),
      },
      {
        id: 'tasks-create',
        method: 'POST',
        path: '/api/tasks',
        title: '创建任务',
        description: '创建新的定时任务',
        auth: 'jwt',
        bodyParams: [
          { name: 'name', type: 'string', required: true, description: '任务名称', example: '签到任务' },
          { name: 'command', type: 'string', required: true, description: '执行脚本', example: 'sign.py' },
          { name: 'schedule', type: 'string', required: true, description: 'Cron 表达式', example: '0 9 * * *' },
          { name: 'timeout', type: 'integer', description: '超时时间（秒）', example: '300' },
          { name: 'max_retries', type: 'integer', description: '最大重试次数', example: '0' },
          { name: 'retry_interval', type: 'integer', description: '重试间隔（秒）', example: '5' },
          { name: 'notify_on_failure', type: 'boolean', description: '失败时通知', example: 'true' },
        ],
        responseExample: JSON.stringify({ message: '创建成功', data: { id: 1, name: '签到任务' } }, null, 2),
      },
      {
        id: 'tasks-update',
        method: 'PUT',
        path: '/api/tasks/:id',
        title: '更新任务',
        description: '更新指定任务的配置',
        auth: 'jwt',
        pathParams: [
          { name: 'id', type: 'integer', required: true, description: '任务 ID' },
        ],
        bodyParams: [
          { name: 'name', type: 'string', description: '任务名称' },
          { name: 'command', type: 'string', description: '执行脚本' },
          { name: 'schedule', type: 'string', description: 'Cron 表达式' },
          { name: 'status', type: 'integer', description: '状态：1=启用, 0=禁用' },
        ],
        responseExample: JSON.stringify({ message: '更新成功' }, null, 2),
      },
      {
        id: 'tasks-delete',
        method: 'DELETE',
        path: '/api/tasks/:id',
        title: '删除任务',
        description: '删除指定任务',
        auth: 'jwt',
        pathParams: [
          { name: 'id', type: 'integer', required: true, description: '任务 ID' },
        ],
        responseExample: JSON.stringify({ message: '删除成功' }, null, 2),
      },
      {
        id: 'tasks-run',
        method: 'POST',
        path: '/api/tasks/:id/run',
        title: '立即执行任务',
        description: '立即触发执行指定任务',
        auth: 'jwt',
        pathParams: [
          { name: 'id', type: 'integer', required: true, description: '任务 ID' },
        ],
        responseExample: JSON.stringify({ message: '任务已开始执行' }, null, 2),
      },
      {
        id: 'tasks-stop',
        method: 'POST',
        path: '/api/tasks/:id/stop',
        title: '停止任务',
        description: '停止正在执行的任务',
        auth: 'jwt',
        pathParams: [
          { name: 'id', type: 'integer', required: true, description: '任务 ID' },
        ],
        responseExample: JSON.stringify({ message: '任务已停止' }, null, 2),
      },
    ],
  },
  {
    key: 'logs',
    label: '执行日志',
    endpoints: [
      {
        id: 'logs-list',
        method: 'GET',
        path: '/api/logs',
        title: '获取日志列表',
        description: '获取任务执行日志，支持按状态过滤和分页',
        auth: 'jwt',
        queryParams: [
          { name: 'status', type: 'integer', description: '状态过滤：0=成功, 1=失败' },
          { name: 'page', type: 'integer', description: '页码', example: '1' },
          { name: 'page_size', type: 'integer', description: '每页数量', example: '20' },
        ],
        responseExample: JSON.stringify({
          data: [{
            id: 1, task_id: 1, task_name: '签到任务',
            status: 0, content: '执行成功',
            duration: 2.5, started_at: '2026-03-10T09:00:00',
          }],
          total: 1,
        }, null, 2),
      },
      {
        id: 'logs-detail',
        method: 'GET',
        path: '/api/logs/:id',
        title: '获取日志详情',
        description: '获取单条日志的详细内容',
        auth: 'jwt',
        pathParams: [
          { name: 'id', type: 'integer', required: true, description: '日志 ID' },
        ],
        responseExample: JSON.stringify({
          data: {
            id: 1, task_id: 1, task_name: '签到任务',
            status: 0, content: '签到成功\n获得 10 积分',
            duration: 2.5, started_at: '2026-03-10T09:00:00', ended_at: '2026-03-10T09:00:02',
          },
        }, null, 2),
      },
      {
        id: 'logs-delete',
        method: 'DELETE',
        path: '/api/logs/:id',
        title: '删除日志',
        description: '删除指定日志记录',
        auth: 'jwt',
        pathParams: [
          { name: 'id', type: 'integer', required: true, description: '日志 ID' },
        ],
        responseExample: JSON.stringify({ message: '删除成功' }, null, 2),
      },
    ],
  },
  {
    key: 'scripts',
    label: '脚本管理',
    endpoints: [
      {
        id: 'scripts-list',
        method: 'GET',
        path: '/api/scripts',
        title: '获取脚本列表',
        description: '获取所有脚本文件列表',
        auth: 'jwt',
        responseExample: JSON.stringify({
          data: [
            { path: 'sign.py', size: 1024, modified: '2026-03-10T00:00:00' },
          ],
        }, null, 2),
      },
      {
        id: 'scripts-content',
        method: 'GET',
        path: '/api/scripts/content/:path',
        title: '获取脚本内容',
        description: '获取指定脚本的文件内容',
        auth: 'jwt',
        pathParams: [
          { name: 'path', type: 'string', required: true, description: '脚本路径', example: 'sign.py' },
        ],
        responseExample: JSON.stringify({
          data: { path: 'sign.py', content: 'print("hello")', size: 15 },
        }, null, 2),
      },
      {
        id: 'scripts-save',
        method: 'PUT',
        path: '/api/scripts/content/:path',
        title: '保存脚本内容',
        description: '创建或更新脚本文件',
        auth: 'jwt',
        pathParams: [
          { name: 'path', type: 'string', required: true, description: '脚本路径' },
        ],
        bodyParams: [
          { name: 'content', type: 'string', required: true, description: '脚本内容' },
        ],
        responseExample: JSON.stringify({ message: '保存成功' }, null, 2),
      },
      {
        id: 'scripts-delete',
        method: 'DELETE',
        path: '/api/scripts/:path',
        title: '删除脚本',
        description: '删除指定脚本文件',
        auth: 'jwt',
        pathParams: [
          { name: 'path', type: 'string', required: true, description: '脚本路径' },
        ],
        responseExample: JSON.stringify({ message: '删除成功' }, null, 2),
      },
      {
        id: 'scripts-upload',
        method: 'POST',
        path: '/api/scripts/upload',
        title: '上传脚本',
        description: '上传脚本文件，支持 .py/.js/.sh/.ts',
        auth: 'jwt',
        bodyParams: [
          { name: 'file', type: 'file', required: true, description: '脚本文件（multipart/form-data）' },
        ],
        responseExample: JSON.stringify({ message: '上传成功', data: { path: 'sign.py' } }, null, 2),
      },
    ],
  },
  {
    key: 'envs',
    label: '环境变量',
    endpoints: [
      {
        id: 'envs-list',
        method: 'GET',
        path: '/api/envs',
        title: '获取所有环境变量',
        description: '获取环境变量列表，支持搜索和分页',
        auth: 'jwt',
        queryParams: [
          { name: 'keyword', type: 'string', description: '搜索关键字' },
          { name: 'page', type: 'integer', description: '页码', example: '1' },
          { name: 'page_size', type: 'integer', description: '每页数量', example: '20' },
        ],
        responseExample: JSON.stringify({
          data: [
            { id: 1, name: 'MY_TOKEN', value: 'abc123', enabled: true, remarks: '签到Token' },
          ],
          total: 1,
        }, null, 2),
        responseFields: [
          { name: 'id', type: 'integer', description: '变量 ID' },
          { name: 'name', type: 'string', description: '变量名' },
          { name: 'value', type: 'string', description: '变量值' },
          { name: 'enabled', type: 'boolean', description: '是否启用' },
          { name: 'remarks', type: 'string', description: '备注' },
        ],
      },
      {
        id: 'envs-create',
        method: 'POST',
        path: '/api/envs',
        title: '创建环境变量',
        description: '创建新的环境变量',
        auth: 'jwt',
        bodyParams: [
          { name: 'name', type: 'string', required: true, description: '变量名', example: 'MY_TOKEN' },
          { name: 'value', type: 'string', required: true, description: '变量值', example: 'abc123' },
          { name: 'remarks', type: 'string', description: '备注' },
        ],
        responseExample: JSON.stringify({ message: '创建成功', data: { id: 1 } }, null, 2),
      },
      {
        id: 'envs-update',
        method: 'PUT',
        path: '/api/envs/:id',
        title: '更新环境变量',
        description: '更新指定环境变量',
        auth: 'jwt',
        pathParams: [{ name: 'id', type: 'integer', required: true, description: '变量 ID' }],
        bodyParams: [
          { name: 'name', type: 'string', description: '变量名' },
          { name: 'value', type: 'string', description: '变量值' },
          { name: 'enabled', type: 'boolean', description: '是否启用' },
          { name: 'remarks', type: 'string', description: '备注' },
        ],
        responseExample: JSON.stringify({ message: '更新成功' }, null, 2),
      },
      {
        id: 'envs-delete',
        method: 'DELETE',
        path: '/api/envs/:id',
        title: '删除环境变量',
        description: '删除指定环境变量',
        auth: 'jwt',
        pathParams: [{ name: 'id', type: 'integer', required: true, description: '变量 ID' }],
        responseExample: JSON.stringify({ message: '删除成功' }, null, 2),
      },
    ],
  },
  {
    key: 'subscriptions',
    label: '订阅管理',
    endpoints: [
      {
        id: 'subs-list',
        method: 'GET',
        path: '/api/subscriptions',
        title: '获取订阅列表',
        description: '获取所有仓库订阅',
        auth: 'jwt',
        responseExample: JSON.stringify({
          data: [{
            id: 1, name: '示例仓库', url: 'https://github.com/user/repo.git',
            branch: 'main', schedule: '0 0 * * *', enabled: true,
          }],
        }, null, 2),
      },
      {
        id: 'subs-create',
        method: 'POST',
        path: '/api/subscriptions',
        title: '创建订阅',
        description: '创建新的仓库订阅',
        auth: 'jwt',
        bodyParams: [
          { name: 'name', type: 'string', required: true, description: '订阅名称' },
          { name: 'url', type: 'string', required: true, description: '仓库 URL（HTTP/HTTPS）' },
          { name: 'branch', type: 'string', description: '分支，默认 main', example: 'main' },
          { name: 'schedule', type: 'string', description: 'Cron 表达式', example: '0 0 * * *' },
          { name: 'whitelist', type: 'string', description: '白名单 glob（逗号分隔）' },
          { name: 'blacklist', type: 'string', description: '黑名单 glob（逗号分隔）' },
          { name: 'target_dir', type: 'string', description: '存放子目录' },
        ],
        responseExample: JSON.stringify({ message: '创建成功', data: { id: 1 } }, null, 2),
      },
      {
        id: 'subs-update',
        method: 'PUT',
        path: '/api/subscriptions/:id',
        title: '更新订阅',
        description: '更新指定订阅配置',
        auth: 'jwt',
        pathParams: [{ name: 'id', type: 'integer', required: true, description: '订阅 ID' }],
        responseExample: JSON.stringify({ message: '更新成功' }, null, 2),
      },
      {
        id: 'subs-delete',
        method: 'DELETE',
        path: '/api/subscriptions/:id',
        title: '删除订阅',
        description: '删除指定订阅',
        auth: 'jwt',
        pathParams: [{ name: 'id', type: 'integer', required: true, description: '订阅 ID' }],
        responseExample: JSON.stringify({ message: '删除成功' }, null, 2),
      },
      {
        id: 'subs-pull',
        method: 'POST',
        path: '/api/subscriptions/:id/pull',
        title: '手动拉取订阅',
        description: '立即拉取指定订阅的脚本',
        auth: 'jwt',
        pathParams: [{ name: 'id', type: 'integer', required: true, description: '订阅 ID' }],
        responseExample: JSON.stringify({ message: '拉取成功，拉取 5 个文件，新增 3 个任务' }, null, 2),
      },
    ],
  },
  {
    key: 'notifications',
    label: '通知渠道',
    endpoints: [
      {
        id: 'notify-list',
        method: 'GET',
        path: '/api/notifications',
        title: '获取通知渠道列表',
        description: '获取所有通知渠道配置',
        auth: 'jwt',
        responseExample: JSON.stringify({
          data: [{
            id: 1, name: '钉钉通知', type: 'dingtalk',
            config: { token: '***' }, enabled: true,
          }],
        }, null, 2),
      },
      {
        id: 'notify-create',
        method: 'POST',
        path: '/api/notifications',
        title: '创建通知渠道',
        description: '创建新的通知渠道，支持：webhook / email / telegram / dingtalk / wecom / bark / pushplus / serverchan / feishu',
        auth: 'jwt',
        bodyParams: [
          { name: 'name', type: 'string', required: true, description: '渠道名称' },
          { name: 'type', type: 'string', required: true, description: '渠道类型', example: 'dingtalk' },
          { name: 'config', type: 'object', required: true, description: '渠道配置（各类型字段不同）' },
        ],
        responseExample: JSON.stringify({ message: '创建成功', data: { id: 1 } }, null, 2),
      },
      {
        id: 'notify-update',
        method: 'PUT',
        path: '/api/notifications/:id',
        title: '更新通知渠道',
        description: '更新指定通知渠道',
        auth: 'jwt',
        pathParams: [{ name: 'id', type: 'integer', required: true, description: '渠道 ID' }],
        responseExample: JSON.stringify({ message: '更新成功' }, null, 2),
      },
      {
        id: 'notify-delete',
        method: 'DELETE',
        path: '/api/notifications/:id',
        title: '删除通知渠道',
        description: '删除指定通知渠道',
        auth: 'jwt',
        pathParams: [{ name: 'id', type: 'integer', required: true, description: '渠道 ID' }],
        responseExample: JSON.stringify({ message: '删除成功' }, null, 2),
      },
      {
        id: 'notify-test',
        method: 'POST',
        path: '/api/notifications/:id/test',
        title: '测试发送',
        description: '向指定渠道发送测试通知',
        auth: 'jwt',
        pathParams: [{ name: 'id', type: 'integer', required: true, description: '渠道 ID' }],
        responseExample: JSON.stringify({ message: '测试通知发送成功' }, null, 2),
      },
    ],
  },
  {
    key: 'deps',
    label: '依赖管理',
    endpoints: [
      {
        id: 'deps-python-list',
        method: 'GET',
        path: '/api/deps/python',
        title: '获取 Python 依赖列表',
        description: '获取已安装的 Python 包列表',
        auth: 'jwt',
        responseExample: JSON.stringify({
          data: [{ name: 'requests', version: '2.31.0' }],
        }, null, 2),
      },
      {
        id: 'deps-python-install',
        method: 'POST',
        path: '/api/deps/python/install',
        title: '安装 Python 包',
        description: '安装指定的 Python 包',
        auth: 'jwt',
        bodyParams: [
          { name: 'name', type: 'string', required: true, description: '包名', example: 'requests' },
        ],
        responseExample: JSON.stringify({ message: '安装成功' }, null, 2),
      },
      {
        id: 'deps-python-uninstall',
        method: 'POST',
        path: '/api/deps/python/uninstall',
        title: '卸载 Python 包',
        description: '卸载指定的 Python 包',
        auth: 'jwt',
        bodyParams: [
          { name: 'name', type: 'string', required: true, description: '包名' },
        ],
        responseExample: JSON.stringify({ message: '卸载成功' }, null, 2),
      },
      {
        id: 'deps-node-list',
        method: 'GET',
        path: '/api/deps/node',
        title: '获取 Node 依赖列表',
        description: '获取已安装的 Node 包列表',
        auth: 'jwt',
        responseExample: JSON.stringify({
          data: [{ name: 'axios', version: '1.6.0' }],
        }, null, 2),
      },
      {
        id: 'deps-node-install',
        method: 'POST',
        path: '/api/deps/node/install',
        title: '安装 Node 包',
        description: '安装指定的 Node 包',
        auth: 'jwt',
        bodyParams: [
          { name: 'name', type: 'string', required: true, description: '包名', example: 'axios' },
        ],
        responseExample: JSON.stringify({ message: '安装成功' }, null, 2),
      },
      {
        id: 'deps-node-uninstall',
        method: 'POST',
        path: '/api/deps/node/uninstall',
        title: '卸载 Node 包',
        description: '卸载指定的 Node 包',
        auth: 'jwt',
        bodyParams: [
          { name: 'name', type: 'string', required: true, description: '包名' },
        ],
        responseExample: JSON.stringify({ message: '卸载成功' }, null, 2),
      },
    ],
  },
  {
    key: 'users',
    label: '用户管理',
    endpoints: [
      {
        id: 'users-list',
        method: 'GET',
        path: '/api/users',
        title: '获取用户列表',
        description: '获取所有用户（仅管理员）',
        auth: 'jwt',
        responseExample: JSON.stringify({
          data: [
            { id: 1, username: 'admin', role: 'admin', enabled: true, last_login_at: '2026-03-10T00:00:00' },
          ],
        }, null, 2),
      },
      {
        id: 'users-create',
        method: 'POST',
        path: '/api/users',
        title: '创建用户',
        description: '创建新用户（仅管理员）',
        auth: 'jwt',
        bodyParams: [
          { name: 'username', type: 'string', required: true, description: '用户名' },
          { name: 'password', type: 'string', required: true, description: '密码（至少8位）' },
          { name: 'role', type: 'string', required: true, description: '角色：admin / operator / viewer' },
        ],
        responseExample: JSON.stringify({ message: '创建成功', data: { id: 2 } }, null, 2),
      },
      {
        id: 'users-update',
        method: 'PUT',
        path: '/api/users/:id',
        title: '更新用户',
        description: '更新用户信息（仅管理员）',
        auth: 'jwt',
        pathParams: [{ name: 'id', type: 'integer', required: true, description: '用户 ID' }],
        bodyParams: [
          { name: 'role', type: 'string', description: '角色' },
          { name: 'enabled', type: 'boolean', description: '是否启用' },
          { name: 'password', type: 'string', description: '新密码' },
        ],
        responseExample: JSON.stringify({ message: '更新成功' }, null, 2),
      },
      {
        id: 'users-delete',
        method: 'DELETE',
        path: '/api/users/:id',
        title: '删除用户',
        description: '删除指定用户（仅管理员，不能删除自己）',
        auth: 'jwt',
        pathParams: [{ name: 'id', type: 'integer', required: true, description: '用户 ID' }],
        responseExample: JSON.stringify({ message: '删除成功' }, null, 2),
      },
    ],
  },
  {
    key: 'open',
    label: '开放 API',
    endpoints: [
      {
        id: 'open-apps-list',
        method: 'GET',
        path: '/api/open/apps',
        title: '获取应用列表',
        description: '获取所有开放 API 应用',
        auth: 'jwt',
        responseExample: JSON.stringify({
          data: [{
            id: 1, name: '自动化工具', client_id: 'cid_xxx',
            client_secret: 'cs_xxx', enabled: true, scopes: 'tasks,envs',
          }],
        }, null, 2),
      },
      {
        id: 'open-token',
        method: 'POST',
        path: '/api/open/token',
        title: '获取开放 API Token',
        description: '使用 Client ID 和 Client Secret 获取访问令牌',
        auth: 'none',
        bodyParams: [
          { name: 'client_id', type: 'string', required: true, description: 'Client ID' },
          { name: 'client_secret', type: 'string', required: true, description: 'Client Secret' },
        ],
        responseExample: JSON.stringify({
          access_token: 'eyJhbGciOi...', token_type: 'Bearer', expires_in: 3600,
        }, null, 2),
      },
    ],
  },
  {
    key: 'config',
    label: '系统配置',
    endpoints: [
      {
        id: 'config-get',
        method: 'GET',
        path: '/api/config',
        title: '获取全部系统配置',
        description: '获取所有系统配置项及其值',
        auth: 'jwt',
        responseExample: JSON.stringify({
          data: {
            auto_add_cron: { key: 'auto_add_cron', value: 'true', description: '订阅拉取时自动创建任务' },
            proxy_url: { key: 'proxy_url', value: '', description: '代理地址' },
          },
        }, null, 2),
      },
      {
        id: 'config-update',
        method: 'PUT',
        path: '/api/config',
        title: '批量更新配置',
        description: '批量更新系统配置（仅管理员）',
        auth: 'jwt',
        bodyParams: [
          { name: 'configs', type: 'object', required: true, description: '配置键值对', example: '{ "proxy_url": "http://127.0.0.1:7890" }' },
        ],
        responseExample: JSON.stringify({ message: '配置已保存' }, null, 2),
      },
    ],
  },
  {
    key: 'system',
    label: '系统信息',
    endpoints: [
      {
        id: 'system-info',
        method: 'GET',
        path: '/api/system/info',
        title: '获取系统信息',
        description: '获取服务器系统信息（CPU/内存/磁盘等）',
        auth: 'jwt',
        responseExample: JSON.stringify({
          data: {
            hostname: 'server', platform: 'Linux', python: '3.10.12',
            cpu_percent: 25.0, cpu_count: 4,
            memory_total: 8589934592, memory_used: 4294967296, memory_percent: 50.0,
            disk_total: 107374182400, disk_used: 53687091200, disk_percent: 50.0,
          },
        }, null, 2),
      },
      {
        id: 'system-stats',
        method: 'GET',
        path: '/api/system/stats',
        title: '获取面板统计',
        description: '获取任务、日志、脚本的统计数据',
        auth: 'jwt',
        responseExample: JSON.stringify({
          data: {
            tasks: { total: 10, enabled: 8, disabled: 2, running: 1 },
            logs: { total: 100, success: 90, failed: 10, success_rate: 90.0 },
            scripts_count: 15,
          },
        }, null, 2),
      },
    ],
  },
]

/** 生成请求示例代码 */
export function generateCodeExamples(endpoint: ApiEndpoint): Record<string, string> {
  const { method, path, bodyParams, auth } = endpoint
  const url = `http://localhost:5000${path}`
  const hasBody = bodyParams && bodyParams.length > 0 && method !== 'GET'

  const bodyObj: Record<string, any> = {}
  if (hasBody) {
    bodyParams!.forEach(p => {
      if (p.example) {
        bodyObj[p.name] = p.type === 'integer' ? Number(p.example) :
          p.type === 'boolean' ? p.example === 'true' : p.example
      } else {
        bodyObj[p.name] = p.type === 'integer' ? 0 : p.type === 'boolean' ? false : ''
      }
    })
  }
  const bodyJson = JSON.stringify(bodyObj, null, 2)

  const authHeader = auth === 'jwt' ? `-H "Authorization: Bearer <TOKEN>"` : ''
  const authHeaderPy = auth === 'jwt' ? `"Authorization": "Bearer <TOKEN>"` : ''

  // Shell (curl)
  let shell = `curl -X ${method} "${url}"`
  if (authHeader) shell += ` \\\n  ${authHeader}`
  if (hasBody) shell += ` \\\n  -H "Content-Type: application/json" \\\n  -d '${bodyJson}'`

  // JavaScript (fetch)
  let js = `const res = await fetch("${url}", {\n  method: "${method}",\n  headers: {\n    "Content-Type": "application/json",`
  if (auth === 'jwt') js += `\n    "Authorization": "Bearer <TOKEN>",`
  js += `\n  },`
  if (hasBody) js += `\n  body: JSON.stringify(${bodyJson}),`
  js += `\n})\nconst data = await res.json()\nconsole.log(data)`

  // Python (requests)
  let python = `import requests\n\n`
  if (auth === 'jwt') python += `headers = {"Authorization": "Bearer <TOKEN>"}\n`
  if (hasBody) {
    python += `data = ${bodyJson}\n`
    python += `res = requests.${method.toLowerCase()}("${url}"${auth === 'jwt' ? ', headers=headers' : ''}, json=data)\n`
  } else {
    python += `res = requests.${method.toLowerCase()}("${url}"${auth === 'jwt' ? ', headers=headers' : ''})\n`
  }
  python += `print(res.json())`

  return { Shell: shell, JavaScript: js, Python: python }
}
