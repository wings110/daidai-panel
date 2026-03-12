import { useEffect, useState } from 'react'
import {
  Card, Typography, Descriptions, Statistic, Row, Col,
  Button, Form, Input, InputNumber, Switch, message, Space, Tag, Tabs,
  Table, Popconfirm, Modal,
} from 'antd'
import {
  ReloadOutlined, LockOutlined, InfoCircleOutlined,
  CheckCircleOutlined, SettingOutlined, SaveOutlined,
  CloudUploadOutlined, CloudDownloadOutlined, DeleteOutlined,
  HistoryOutlined, ExclamationCircleOutlined, SafetyOutlined,
  QrcodeOutlined, KeyOutlined, LoginOutlined, GlobalOutlined,
  ClockCircleOutlined, CheckOutlined, CloseOutlined,
} from '@ant-design/icons'
import { systemApi, authApi, configApi, twoFactorApi, securityApi } from '../../services/api'
import QRCode from 'qrcode'

const { Title, Text } = Typography

interface SystemInfo {
  platform: string
  python: string
  hostname: string
  cpu_percent?: number
  cpu_count?: number
  memory_total?: number
  memory_used?: number
  memory_percent?: number
  disk_total?: number
  disk_used?: number
  disk_percent?: number
  resource_note?: string
}

interface Stats {
  tasks: { total: number; enabled: number; disabled: number; running: number }
  logs: { total: number; success: number; failed: number; success_rate: number }
  scripts_count: number
}

export default function Settings() {
  const [sysInfo, setSysInfo] = useState<SystemInfo | null>(null)
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(false)
  const [pwdLoading, setPwdLoading] = useState(false)
  const [configLoading, setConfigLoading] = useState(false)
  const [configSaving, setConfigSaving] = useState(false)
  const [configs, setConfigs] = useState<Record<string, string>>({})
  const [backups, setBackups] = useState<any[]>([])
  const [backupLoading, setBackupLoading] = useState(false)
  const [backupCreating, setBackupCreating] = useState(false)
  const [pwdForm] = Form.useForm()
  const [configForm] = Form.useForm()
  const [twoFactorEnabled, setTwoFactorEnabled] = useState(false)
  const [twoFactorLoading, setTwoFactorLoading] = useState(false)
  const [qrCodeUrl, setQrCodeUrl] = useState('')
  const [secret, setSecret] = useState('')
  const [backupCodes, setBackupCodes] = useState<string[]>([])
  const [showSetup2FA, setShowSetup2FA] = useState(false)
  const [verifyForm] = Form.useForm()
  const [disableForm] = Form.useForm()
  const [backupCodesForm] = Form.useForm()
  const [loginLogs, setLoginLogs] = useState<any[]>([])
  const [loginLogsLoading, setLoginLogsLoading] = useState(false)
  const [loginLogsTotal, setLoginLogsTotal] = useState(0)
  const [loginLogsPage, setLoginLogsPage] = useState(1)
  const [sessions, setSessions] = useState<any[]>([])
  const [sessionsLoading, setSessionsLoading] = useState(false)
  const [ipWhitelist, setIpWhitelist] = useState<any[]>([])
  const [ipWhitelistLoading, setIpWhitelistLoading] = useState(false)
  const [showAddIP, setShowAddIP] = useState(false)
  const [ipForm] = Form.useForm()

  useEffect(() => {
    fetchData()
    fetchConfigs()
    fetchBackups()
    fetch2FAStatus()
  }, [])

  const fetchData = async () => {
    setLoading(true)
    try {
      const [infoRes, statsRes] = await Promise.all([
        systemApi.getInfo(),
        systemApi.getStats(),
      ])
      setSysInfo(infoRes.data.data)
      setStats(statsRes.data.data)
    } catch {
      // 静默
    } finally {
      setLoading(false)
    }
  }

  const fetchConfigs = async () => {
    setConfigLoading(true)
    try {
      const res = await configApi.getAll()
      const data = res.data.data || {}
      const flat: Record<string, string> = {}
      for (const [k, v] of Object.entries(data)) {
        flat[k] = (v as any).value ?? ''
      }
      setConfigs(flat)
      configForm.setFieldsValue({
        auto_add_cron: flat.auto_add_cron === 'true',
        auto_del_cron: flat.auto_del_cron === 'true',
        default_cron_rule: flat.default_cron_rule || '',
        repo_file_extensions: flat.repo_file_extensions || '',
        proxy_url: flat.proxy_url || '',
        cpu_warn: Number(flat.cpu_warn) || 80,
        memory_warn: Number(flat.memory_warn) || 80,
        disk_warn: Number(flat.disk_warn) || 90,
        command_timeout: Number(flat.command_timeout) || 300,
        max_concurrent_tasks: Number(flat.max_concurrent_tasks) || 5,
        log_retention_days: Number(flat.log_retention_days) || 3,
        random_delay: flat.random_delay || '',
        random_delay_extensions: flat.random_delay_extensions || '',
        notify_on_resource_warn: flat.notify_on_resource_warn === 'true',
        notify_on_login: flat.notify_on_login === 'true',
        geetest_enabled: flat.geetest_enabled === 'true',
        geetest_captcha_id: flat.geetest_captcha_id || '',
        geetest_captcha_key: flat.geetest_captcha_key || '',
      })
    } catch {
      message.error('获取配置失败')
    } finally {
      setConfigLoading(false)
    }
  }

  const handleSaveConfig = async () => {
    try {
      const values = await configForm.validateFields()
      setConfigSaving(true)
      const payload: Record<string, string> = {
        auto_add_cron: values.auto_add_cron ? 'true' : 'false',
        auto_del_cron: values.auto_del_cron ? 'true' : 'false',
        default_cron_rule: values.default_cron_rule || '',
        repo_file_extensions: values.repo_file_extensions || '',
        proxy_url: values.proxy_url || '',
        cpu_warn: String(values.cpu_warn ?? 80),
        memory_warn: String(values.memory_warn ?? 80),
        disk_warn: String(values.disk_warn ?? 90),
        command_timeout: String(values.command_timeout ?? 300),
        max_concurrent_tasks: String(values.max_concurrent_tasks ?? 5),
        log_retention_days: String(values.log_retention_days ?? 3),
        random_delay: values.random_delay || '',
        random_delay_extensions: values.random_delay_extensions || '',
        notify_on_resource_warn: values.notify_on_resource_warn ? 'true' : 'false',
        notify_on_login: values.notify_on_login ? 'true' : 'false',
        geetest_enabled: values.geetest_enabled ? 'true' : 'false',
        geetest_captcha_id: values.geetest_captcha_id || '',
        geetest_captcha_key: values.geetest_captcha_key || '',
      }
      await configApi.update(payload)
      message.success('配置已保存')
      fetchConfigs()
    } catch (err: any) {
      if (err?.response?.data?.error) {
        message.error(err.response.data.error)
      }
    } finally {
      setConfigSaving(false)
    }
  }

  const handleChangePassword = async () => {
    try {
      const values = await pwdForm.validateFields()
      if (values.new_password !== values.confirm_password) {
        message.error('两次输入的密码不一致')
        return
      }
      setPwdLoading(true)
      await authApi.changePassword({ old_password: values.old_password, new_password: values.new_password })
      message.success('密码修改成功')
      pwdForm.resetFields()
    } catch (err: any) {
      if (err?.response?.data?.error) {
        message.error(err.response.data.error)
      }
    } finally {
      setPwdLoading(false)
    }
  }

  const fetchBackups = async () => {
    setBackupLoading(true)
    try {
      const res = await systemApi.listBackups()
      setBackups(res.data.data || [])
    } catch {
      // silent
    } finally {
      setBackupLoading(false)
    }
  }

  const handleCreateBackup = async () => {
    Modal.confirm({
      title: '创建加密备份',
      icon: <CloudUploadOutlined />,
      content: (
        <div>
          <p style={{ marginBottom: 8, color: '#8c8c8c' }}>备份将包含数据库和脚本文件，使用密码加密保护。</p>
          <Input.Password
            id="backup-password-input"
            placeholder="请输入备份密码（至少 8 位）"
            minLength={8}
          />
        </div>
      ),
      okText: '创建备份',
      cancelText: '取消',
      onOk: async () => {
        const input = document.getElementById('backup-password-input') as HTMLInputElement
        const password = input?.value?.trim()
        if (!password) {
          message.error('请输入备份密码')
          throw new Error('cancelled')
        }
        if (password.length < 8) {
          message.error('备份密码至少 8 个字符')
          throw new Error('cancelled')
        }
        try {
          await systemApi.createBackup(password)
          message.success('备份创建成功')
          fetchBackups()
        } catch (err: any) {
          if (err?.message === 'cancelled') throw err
          message.error(err?.response?.data?.error || '备份失败')
          throw err
        }
      },
    })
  }

  const handleDeleteBackup = async (filename: string) => {
    try {
      await systemApi.deleteBackup(filename)
      message.success('备份已删除')
      fetchBackups()
    } catch {
      message.error('删除失败')
    }
  }

  const handleRestore = (filename: string) => {
    const isEncrypted = filename.endsWith('.enc')
    Modal.confirm({
      title: '确认恢复数据',
      icon: <ExclamationCircleOutlined />,
      content: (
        <div>
          <p style={{ color: '#ff4d4f', marginBottom: 8 }}>恢复将覆盖当前数据库和脚本文件，恢复后需要重启面板。</p>
          {isEncrypted && (
            <Input.Password
              id="restore-password-input"
              placeholder="请输入备份密码"
              style={{ marginTop: 8 }}
            />
          )}
        </div>
      ),
      okText: '确认恢复',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        let password: string | undefined
        if (isEncrypted) {
          const input = document.getElementById('restore-password-input') as HTMLInputElement
          password = input?.value?.trim()
          if (!password) {
            message.error('请输入备份密码')
            throw new Error('cancelled')
          }
        }
        try {
          const res = await systemApi.restore(filename, password)
          message.success(res.data.message || '恢复成功')
        } catch (err: any) {
          if (err?.message === 'cancelled') throw err
          message.error(err?.response?.data?.error || '恢复失败')
          throw err
        }
      },
    })
  }

  const handleDownloadBackup = (filename: string) => {
    const token = localStorage.getItem('access_token')
    window.open(`/api/system/backup/download/${filename}?token=${token}`, '_blank')
  }

  // ==================== 双因素认证相关 ====================

  const fetch2FAStatus = async () => {
    try {
      const res = await twoFactorApi.getStatus()
      setTwoFactorEnabled(res.data.enabled || false)
    } catch {
      // 静默
    }
  }

  const handleSetup2FA = async () => {
    setTwoFactorLoading(true)
    try {
      const res = await twoFactorApi.setup()
      const { secret: newSecret, totp_uri } = res.data
      setSecret(newSecret)

      // 生成二维码
      const qrUrl = await QRCode.toDataURL(totp_uri)
      setQrCodeUrl(qrUrl)
      setShowSetup2FA(true)
    } catch (err: any) {
      message.error(err?.response?.data?.error || '设置失败')
    } finally {
      setTwoFactorLoading(false)
    }
  }

  const handleEnable2FA = async () => {
    try {
      const values = await verifyForm.validateFields()
      setTwoFactorLoading(true)
      const res = await twoFactorApi.enable(values.token)
      setBackupCodes(res.data.backup_codes || [])
      setTwoFactorEnabled(true)
      message.success('双因素认证已启用')
      verifyForm.resetFields()
    } catch (err: any) {
      message.error(err?.response?.data?.error || '启用失败')
    } finally {
      setTwoFactorLoading(false)
    }
  }

  const handleDisable2FA = async () => {
    try {
      const values = await disableForm.validateFields()
      setTwoFactorLoading(true)
      await twoFactorApi.disable(values.password)
      setTwoFactorEnabled(false)
      setShowSetup2FA(false)
      setQrCodeUrl('')
      setSecret('')
      setBackupCodes([])
      message.success('双因素认证已禁用')
      disableForm.resetFields()
    } catch (err: any) {
      message.error(err?.response?.data?.error || '禁用失败')
    } finally {
      setTwoFactorLoading(false)
    }
  }

  const handleRegenerateBackupCodes = async () => {
    try {
      const values = await backupCodesForm.validateFields()
      setTwoFactorLoading(true)
      const res = await twoFactorApi.regenerateBackupCodes(values.password)
      setBackupCodes(res.data.backup_codes || [])
      message.success('备用码已重新生成')
      backupCodesForm.resetFields()
    } catch (err: any) {
      message.error(err?.response?.data?.error || '生成失败')
    } finally {
      setTwoFactorLoading(false)
    }
  }

  const handleCopyBackupCodes = () => {
    const text = backupCodes.join('\n')
    navigator.clipboard.writeText(text)
    message.success('备用码已复制到剪贴板')
  }

  // ==================== 登录日志相关 ====================

  const fetchLoginLogs = async (page: number = 1) => {
    setLoginLogsLoading(true)
    try {
      const res = await securityApi.listLoginLogs({ page, page_size: 20 })
      setLoginLogs(res.data.data || [])
      setLoginLogsTotal(res.data.total || 0)
      setLoginLogsPage(page)
    } catch {
      message.error('获取登录日志失败')
    } finally {
      setLoginLogsLoading(false)
    }
  }

  const handleCleanLoginLogs = async () => {
    try {
      await securityApi.cleanLoginLogs(90)
      message.success('已清理90天前的登录日志')
      fetchLoginLogs(1)
    } catch {
      message.error('清理失败')
    }
  }

  // ==================== 会话管理相关 ====================

  const fetchSessions = async () => {
    setSessionsLoading(true)
    try {
      const res = await securityApi.listSessions()
      setSessions(res.data.data || [])
    } catch {
      message.error('获取会话列表失败')
    } finally {
      setSessionsLoading(false)
    }
  }

  const handleRevokeSession = async (sessionId: number) => {
    try {
      await securityApi.revokeSession(sessionId)
      message.success('会话已撤销')
      fetchSessions()
    } catch {
      message.error('撤销失败')
    }
  }

  const handleRevokeAllSessions = async () => {
    Modal.confirm({
      title: '确认撤销所有其他会话？',
      content: '这将强制其他设备退出登录',
      onOk: async () => {
        try {
          await securityApi.revokeAllSessions()
          message.success('已撤销所有其他会话')
          fetchSessions()
        } catch {
          message.error('撤销失败')
        }
      },
    })
  }

  // ==================== IP白名单相关 ====================

  const fetchIPWhitelist = async () => {
    setIpWhitelistLoading(true)
    try {
      const res = await securityApi.listIPWhitelist()
      setIpWhitelist(res.data.data || [])
    } catch {
      message.error('获取IP白名单失败')
    } finally {
      setIpWhitelistLoading(false)
    }
  }

  const handleAddIP = async () => {
    try {
      const values = await ipForm.validateFields()
      await securityApi.addIPWhitelist(values)
      message.success('添加成功')
      setShowAddIP(false)
      ipForm.resetFields()
      fetchIPWhitelist()
    } catch (err: any) {
      if (err?.response?.data?.error) {
        message.error(err.response.data.error)
      }
    }
  }

  const handleToggleIP = async (id: number, enabled: boolean) => {
    try {
      await securityApi.updateIPWhitelist(id, { enabled })
      message.success(enabled ? '已启用' : '已禁用')
      fetchIPWhitelist()
    } catch {
      message.error('操作失败')
    }
  }

  const handleDeleteIP = async (id: number) => {
    try {
      await securityApi.deleteIPWhitelist(id)
      message.success('删除成功')
      fetchIPWhitelist()
    } catch {
      message.error('删除失败')
    }
  }

  const formatBytes = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`
  }

  const tabItems = [
    {
      key: 'overview',
      label: '概览',
      children: (
        <>
          {/* 面板统计 */}
          {stats && (
            <Card title={<Space><InfoCircleOutlined />面板概况</Space>} style={{ borderRadius: 10, marginBottom: 20 }}>
              <Row gutter={[24, 16]}>
                <Col xs={8} sm={6} md={4}>
                  <Statistic title="任务总数" value={stats.tasks.total} />
                </Col>
                <Col xs={8} sm={6} md={4}>
                  <Statistic title="已启用" value={stats.tasks.enabled} valueStyle={{ color: '#52c41a' }} />
                </Col>
                <Col xs={8} sm={6} md={4}>
                  <Statistic title="运行中" value={stats.tasks.running} valueStyle={{ color: '#faad14' }} />
                </Col>
                <Col xs={8} sm={6} md={4}>
                  <Statistic title="执行日志" value={stats.logs.total} />
                </Col>
                <Col xs={8} sm={6} md={4}>
                  <Statistic title="成功率" value={stats.logs.success_rate} suffix="%" valueStyle={{ color: '#52c41a' }} />
                </Col>
                <Col xs={8} sm={6} md={4}>
                  <Statistic title="脚本数" value={stats.scripts_count} />
                </Col>
              </Row>
            </Card>
          )}

          {/* 系统信息 */}
          {sysInfo && (
            <Card title={<Space><InfoCircleOutlined />系统信息</Space>} style={{ borderRadius: 10 }}>
              <Descriptions column={{ xs: 1, sm: 2, md: 3 }} size="small">
                <Descriptions.Item label="主机名">{sysInfo.hostname}</Descriptions.Item>
                <Descriptions.Item label="操作系统">{sysInfo.platform}</Descriptions.Item>
                <Descriptions.Item label="Python">{sysInfo.python}</Descriptions.Item>
                {sysInfo.cpu_percent !== undefined && (
                  <>
                    <Descriptions.Item label="CPU 使用率">
                      <Tag color={sysInfo.cpu_percent > 80 ? 'red' : sysInfo.cpu_percent > 50 ? 'orange' : 'green'}>
                        {sysInfo.cpu_percent}%
                      </Tag>
                      <Text type="secondary"> ({sysInfo.cpu_count} 核)</Text>
                    </Descriptions.Item>
                    <Descriptions.Item label="内存使用">
                      <Tag color={sysInfo.memory_percent! > 80 ? 'red' : sysInfo.memory_percent! > 50 ? 'orange' : 'green'}>
                        {sysInfo.memory_percent}%
                      </Tag>
                      <Text type="secondary"> ({formatBytes(sysInfo.memory_used!)} / {formatBytes(sysInfo.memory_total!)})</Text>
                    </Descriptions.Item>
                    <Descriptions.Item label="磁盘使用">
                      <Tag color={sysInfo.disk_percent! > 80 ? 'red' : sysInfo.disk_percent! > 50 ? 'orange' : 'green'}>
                        {sysInfo.disk_percent}%
                      </Tag>
                      <Text type="secondary"> ({formatBytes(sysInfo.disk_used!)} / {formatBytes(sysInfo.disk_total!)})</Text>
                    </Descriptions.Item>
                  </>
                )}
                {sysInfo.resource_note && (
                  <Descriptions.Item label="提示">
                    <Text type="secondary">{sysInfo.resource_note}</Text>
                  </Descriptions.Item>
                )}
              </Descriptions>
            </Card>
          )}
        </>
      ),
    },
    {
      key: 'config',
      label: '系统配置',
      children: (
        <Card
          title={<Space><SettingOutlined />系统配置</Space>}
          style={{ borderRadius: 10 }}
          loading={configLoading}
          extra={
            <Button type="primary" icon={<SaveOutlined />} loading={configSaving} onClick={handleSaveConfig}>
              保存配置
            </Button>
          }
        >
          <Form form={configForm} layout="vertical" style={{ maxWidth: 600 }}>
            <Title level={5} style={{ marginBottom: 16 }}>订阅设置</Title>
            <Row gutter={16}>
              <Col span={12}>
                <Form.Item name="auto_add_cron" label="自动添加定时任务" valuePropName="checked">
                  <Switch checkedChildren="开" unCheckedChildren="关" />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item name="auto_del_cron" label="自动删除失效任务" valuePropName="checked">
                  <Switch checkedChildren="开" unCheckedChildren="关" />
                </Form.Item>
              </Col>
            </Row>
            <Form.Item name="default_cron_rule" label="默认 Cron 规则" extra="匹配不到定时规则时使用，如 0 9 * * *">
              <Input placeholder="0 9 * * *" />
            </Form.Item>
            <Form.Item name="repo_file_extensions" label="拉取文件后缀" extra="空格分隔，如 py js sh ts">
              <Input placeholder="py js sh ts" />
            </Form.Item>

            <Title level={5} style={{ marginBottom: 16, marginTop: 8 }}>资源告警</Title>
            <Row gutter={16}>
              <Col span={8}>
                <Form.Item name="cpu_warn" label="CPU 阈值 (%)">
                  <InputNumber min={1} max={100} style={{ width: '100%' }} />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item name="memory_warn" label="内存阈值 (%)">
                  <InputNumber min={1} max={100} style={{ width: '100%' }} />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item name="disk_warn" label="磁盘阈值 (%)">
                  <InputNumber min={1} max={100} style={{ width: '100%' }} />
                </Form.Item>
              </Col>
            </Row>
            <Form.Item name="notify_on_resource_warn" label="资源超限发送通知" valuePropName="checked">
              <Switch checkedChildren="开" unCheckedChildren="关" />
            </Form.Item>
            <Form.Item name="notify_on_login" label="登录成功发送通知" valuePropName="checked" extra="开启后，每次登录成功将向所有已启用的通知渠道发送通知">
              <Switch checkedChildren="开" unCheckedChildren="关" />
            </Form.Item>
          </Form>
        </Card>
      ),
    },
    {
      key: 'task-exec',
      label: '任务执行',
      children: (
        <Card
          title={<Space><ClockCircleOutlined />任务执行</Space>}
          style={{ borderRadius: 10 }}
          loading={configLoading}
          extra={
            <Button type="primary" icon={<SaveOutlined />} loading={configSaving} onClick={handleSaveConfig}>
              保存配置
            </Button>
          }
        >
          <Form form={configForm} layout="vertical" style={{ maxWidth: 600 }}>
            <Form.Item name="command_timeout" label="全局默认超时（秒）" extra="单个任务未设超时时使用此值">
              <InputNumber min={10} max={86400} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="max_concurrent_tasks" label="定时任务并发数" extra="同时执行的最大任务数量">
              <InputNumber min={1} max={200} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="log_retention_days" label="日志删除频率" extra="自动删除超过指定天数的任务日志（每天凌晨 3 点执行）">
              <InputNumber min={1} max={365} style={{ width: '100%' }} addonBefore="每" addonAfter="天" />
            </Form.Item>
            <Form.Item name="random_delay" label="随机延迟最大秒数" extra="留空或 0 表示不延迟">
              <Input placeholder="如 300 表示 1~300 秒随机延迟" />
            </Form.Item>
            <Form.Item name="random_delay_extensions" label="延迟文件后缀" extra="空格分隔，留空表示全部任务">
              <Input placeholder="如 js py" />
            </Form.Item>
          </Form>
        </Card>
      ),
    },
    {
      key: 'proxy',
      label: '网络代理',
      children: (
        <Card
          title={<Space><GlobalOutlined />网络代理</Space>}
          style={{ borderRadius: 10 }}
          loading={configLoading}
          extra={
            <Button type="primary" icon={<SaveOutlined />} loading={configSaving} onClick={handleSaveConfig}>
              保存配置
            </Button>
          }
        >
          <Form form={configForm} layout="vertical" style={{ maxWidth: 600 }}>
            <Form.Item name="proxy_url" label="代理地址" extra="支持 HTTP/SOCKS5，如 http://127.0.0.1:7890">
              <Input placeholder="http://127.0.0.1:7890" />
            </Form.Item>
          </Form>
        </Card>
      ),
    },
    {
      key: 'captcha',
      label: '验证码设置',
      children: (
        <Card
          title={<Space><SafetyOutlined />验证码设置</Space>}
          style={{ borderRadius: 10 }}
          loading={configLoading}
          extra={
            <Button type="primary" icon={<SaveOutlined />} loading={configSaving} onClick={handleSaveConfig}>
              保存配置
            </Button>
          }
        >
          <Form form={configForm} layout="vertical" style={{ maxWidth: 600 }}>
            <Form.Item name="geetest_enabled" label="启用极验验证码" valuePropName="checked" extra="开启后，登录密码输错 3 次将触发极验 V4 验证码">
              <Switch checkedChildren="开" unCheckedChildren="关" />
            </Form.Item>
            <Form.Item name="geetest_captcha_id" label="Captcha ID" extra="极验后台获取的 Captcha ID">
              <Input placeholder="请输入极验 Captcha ID" />
            </Form.Item>
            <Form.Item name="geetest_captcha_key" label="Captcha Key" extra="极验后台获取的 Captcha Key（服务端密钥）">
              <Input.Password placeholder="请输入极验 Captcha Key" />
            </Form.Item>
          </Form>
        </Card>
      ),
    },
    {
      key: 'backup',
      label: '数据备份',
      children: (
        <Card
          title={<Space><HistoryOutlined />数据备份与恢复</Space>}
          style={{ borderRadius: 10 }}
          extra={
            <Button type="primary" icon={<CloudUploadOutlined />} onClick={handleCreateBackup}>
              创建备份
            </Button>
          }
        >
          <Table
            dataSource={backups}
            rowKey="filename"
            loading={backupLoading}
            size="middle"
            locale={{ emptyText: '暂无备份' }}
            pagination={false}
            columns={[
              {
                title: '文件名',
                dataIndex: 'filename',
                key: 'filename',
                ellipsis: true,
              },
              {
                title: '大小',
                dataIndex: 'size',
                key: 'size',
                width: 100,
                render: (v: number) => formatBytes(v),
              },
              {
                title: '创建时间',
                dataIndex: 'created_at',
                key: 'created_at',
                width: 180,
                render: (v: number) => {
                  const d = new Date(v * 1000)
                  return d.toLocaleString('zh-CN')
                },
              },
              {
                title: '操作',
                key: 'actions',
                width: 200,
                render: (_: any, record: any) => (
                  <Space size={4}>
                    <Button type="text" size="small" icon={<CloudDownloadOutlined />} onClick={() => handleDownloadBackup(record.filename)}>下载</Button>
                    <Button type="text" size="small" icon={<HistoryOutlined />} onClick={() => handleRestore(record.filename)}>恢复</Button>
                    <Popconfirm title="确定删除？" onConfirm={() => handleDeleteBackup(record.filename)}>
                      <Button type="text" size="small" icon={<DeleteOutlined />} danger />
                    </Popconfirm>
                  </Space>
                ),
              },
            ]}
          />
        </Card>
      ),
    },
    {
      key: 'security',
      label: '安全',
      children: (
        <Tabs
          defaultActiveKey="password"
          items={[
            {
              key: 'password',
              label: <span><LockOutlined />密码与2FA</span>,
              children: (
                <Space direction="vertical" size="large" style={{ width: '100%' }}>
                  {/* 修改密码 */}
                  <Card
                    title={<Space><LockOutlined />修改密码</Space>}
                    style={{ borderRadius: 10, maxWidth: 480 }}
                  >
                    <Form form={pwdForm} layout="vertical" onFinish={handleChangePassword}>
                      <Form.Item
                        name="old_password"
                        label="当前密码"
                        rules={[{ required: true, message: '请输入当前密码' }]}
                      >
                        <Input.Password placeholder="当前密码" />
                      </Form.Item>
                      <Form.Item
                        name="new_password"
                        label="新密码"
                        rules={[
                          { required: true, message: '请输入新密码' },
                          { min: 8, message: '密码至少 8 个字符' },
                        ]}
                      >
                        <Input.Password placeholder="新密码（至少 8 位）" />
                      </Form.Item>
                      <Form.Item
                        name="confirm_password"
                        label="确认密码"
                        rules={[{ required: true, message: '请确认新密码' }]}
                      >
                        <Input.Password placeholder="再次输入新密码" />
                      </Form.Item>
                      <Form.Item>
                        <Button type="primary" htmlType="submit" loading={pwdLoading} icon={<CheckCircleOutlined />}>
                          修改密码
                        </Button>
                      </Form.Item>
                    </Form>
                  </Card>

                  {/* 双因素认证 */}
                  <Card
                    title={<Space><SafetyOutlined />双因素认证 (2FA)</Space>}
                    style={{ borderRadius: 10, maxWidth: 600 }}
                    extra={
                      twoFactorEnabled ? (
                        <Tag color="success" icon={<CheckCircleOutlined />}>已启用</Tag>
                      ) : (
                        <Tag color="default">未启用</Tag>
                      )
                    }
                  >
                    {!twoFactorEnabled ? (
                      <>
                        <Text type="secondary" style={{ display: 'block', marginBottom: 16 }}>
                          双因素认证为您的账户提供额外的安全保护。启用后，登录时除了密码外，还需要输入认证器应用生成的验证码。
                        </Text>
                        <Button
                          type="primary"
                          icon={<QrcodeOutlined />}
                          loading={twoFactorLoading}
                          onClick={handleSetup2FA}
                        >
                          启用双因素认证
                        </Button>

                        {/* 设置2FA的Modal */}
                        <Modal
                          title="设置双因素认证"
                          open={showSetup2FA}
                          onCancel={() => {
                            setShowSetup2FA(false)
                            setQrCodeUrl('')
                            setSecret('')
                            verifyForm.resetFields()
                          }}
                          footer={null}
                          width={500}
                        >
                          {!backupCodes.length ? (
                            <>
                              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                                <div>
                                  <Text strong>步骤 1: 扫描二维码</Text>
                                  <div style={{ marginTop: 12, textAlign: 'center' }}>
                                    {qrCodeUrl && <img src={qrCodeUrl} alt="QR Code" style={{ width: 200, height: 200 }} />}
                                  </div>
                                  <Text type="secondary" style={{ display: 'block', marginTop: 8, fontSize: 12 }}>
                                    使用 Google Authenticator、Microsoft Authenticator 或其他 TOTP 认证器应用扫描此二维码
                                  </Text>
                                </div>

                                <div>
                                  <Text strong>或手动输入密钥:</Text>
                                  <Input.Password
                                    value={secret}
                                    readOnly
                                    style={{ marginTop: 8 }}
                                    addonAfter={
                                      <Button
                                        type="link"
                                        size="small"
                                        onClick={() => {
                                          navigator.clipboard.writeText(secret)
                                          message.success('密钥已复制')
                                        }}
                                      >
                                        复制
                                      </Button>
                                    }
                                  />
                                </div>

                                <div>
                                  <Text strong>步骤 2: 输入验证码</Text>
                                  <Form form={verifyForm} onFinish={handleEnable2FA} style={{ marginTop: 12 }}>
                                    <Form.Item
                                      name="token"
                                      rules={[{ required: true, message: '请输入验证码' }]}
                                    >
                                      <Input
                                        placeholder="输入认证器中的 6 位验证码"
                                        maxLength={6}
                                        size="large"
                                      />
                                    </Form.Item>
                                    <Form.Item>
                                      <Button type="primary" htmlType="submit" loading={twoFactorLoading} block>
                                        验证并启用
                                      </Button>
                                    </Form.Item>
                                  </Form>
                                </div>
                              </Space>
                            </>
                          ) : (
                            <>
                              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                                <div>
                                  <Text strong style={{ color: '#52c41a' }}>
                                    <CheckCircleOutlined /> 双因素认证已成功启用！
                                  </Text>
                                </div>

                                <div>
                                  <Text strong>备用码</Text>
                                  <Text type="secondary" style={{ display: 'block', marginTop: 4, fontSize: 12 }}>
                                    请妥善保存这些备用码。当您无法使用认证器时，可以使用备用码登录。每个备用码只能使用一次。
                                  </Text>
                                  <div style={{
                                    marginTop: 12,
                                    padding: 16,
                                    background: '#f5f5f5',
                                    borderRadius: 8,
                                    fontFamily: 'monospace',
                                  }}>
                                    {backupCodes.map((code, idx) => (
                                      <div key={idx} style={{ marginBottom: 4 }}>
                                        {code}
                                      </div>
                                    ))}
                                  </div>
                                  <Button
                                    icon={<KeyOutlined />}
                                    onClick={handleCopyBackupCodes}
                                    style={{ marginTop: 12 }}
                                  >
                                    复制备用码
                                  </Button>
                                </div>

                                <Button
                                  type="primary"
                                  block
                                  onClick={() => {
                                    setShowSetup2FA(false)
                                    setQrCodeUrl('')
                                    setSecret('')
                                    setBackupCodes([])
                                    verifyForm.resetFields()
                                  }}
                                >
                                  完成
                                </Button>
                              </Space>
                            </>
                          )}
                        </Modal>
                      </>
                    ) : (
                      <>
                        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                          <div>
                            <Text type="secondary">
                              您的账户已启用双因素认证保护。登录时需要输入认证器应用生成的验证码。
                            </Text>
                          </div>

                          {/* 重新生成备用码 */}
                          <Card size="small" title="重新生成备用码" style={{ marginTop: 16 }}>
                            <Text type="secondary" style={{ display: 'block', marginBottom: 12, fontSize: 12 }}>
                              如果您丢失了备用码或已使用完，可以重新生成。旧的备用码将失效。
                            </Text>
                            <Form form={backupCodesForm} layout="inline" onFinish={handleRegenerateBackupCodes}>
                              <Form.Item
                                name="password"
                                rules={[{ required: true, message: '请输入密码' }]}
                                style={{ flex: 1 }}
                              >
                                <Input.Password placeholder="输入密码以确认" />
                              </Form.Item>
                              <Form.Item>
                                <Button type="primary" htmlType="submit" loading={twoFactorLoading} icon={<KeyOutlined />}>
                                  重新生成
                                </Button>
                              </Form.Item>
                            </Form>

                            {backupCodes.length > 0 && (
                              <div style={{ marginTop: 16 }}>
                                <Text strong>新的备用码：</Text>
                                <div style={{
                                  marginTop: 8,
                                  padding: 12,
                                  background: '#f5f5f5',
                                  borderRadius: 8,
                                  fontFamily: 'monospace',
                                  fontSize: 12,
                                }}>
                                  {backupCodes.map((code, idx) => (
                                    <div key={idx} style={{ marginBottom: 4 }}>
                                      {code}
                                    </div>
                                  ))}
                                </div>
                                <Button
                                  size="small"
                                  icon={<KeyOutlined />}
                                  onClick={handleCopyBackupCodes}
                                  style={{ marginTop: 8 }}
                                >
                                  复制备用码
                                </Button>
                              </div>
                            )}
                          </Card>

                          {/* 禁用2FA */}
                          <Card size="small" title="禁用双因素认证" style={{ marginTop: 16 }}>
                            <Text type="secondary" style={{ display: 'block', marginBottom: 12, fontSize: 12 }}>
                              禁用后，登录时将不再需要验证码。这会降低账户安全性。
                            </Text>
                            <Form form={disableForm} layout="inline" onFinish={handleDisable2FA}>
                              <Form.Item
                                name="password"
                                rules={[{ required: true, message: '请输入密码' }]}
                                style={{ flex: 1 }}
                              >
                                <Input.Password placeholder="输入密码以确认" />
                              </Form.Item>
                              <Form.Item>
                                <Button danger htmlType="submit" loading={twoFactorLoading}>
                                  禁用
                                </Button>
                              </Form.Item>
                            </Form>
                          </Card>
                        </Space>
                      </>
                    )}
                  </Card>
                </Space>
              ),
            },
            {
              key: 'loginLogs',
              label: <span><LoginOutlined />登录日志</span>,
              children: (
                <Card
                  title={<Space><LoginOutlined />登录日志</Space>}
                  style={{ borderRadius: 10 }}
                  extra={
                    <Space>
                      <Button icon={<ReloadOutlined />} onClick={() => fetchLoginLogs(1)}>刷新</Button>
                      <Popconfirm title="确定清理90天前的日志？" onConfirm={handleCleanLoginLogs}>
                        <Button icon={<DeleteOutlined />}>清理旧日志</Button>
                      </Popconfirm>
                    </Space>
                  }
                >
                  <Table
                    dataSource={loginLogs}
                    rowKey="id"
                    loading={loginLogsLoading}
                    scroll={{ y: 500 }}
                    virtual
                    pagination={{
                      current: loginLogsPage,
                      pageSize: 20,
                      total: loginLogsTotal,
                      onChange: fetchLoginLogs,
                      showSizeChanger: false,
                      showTotal: (total) => `共 ${total} 条`,
                    }}
                    columns={[
                      {
                        title: '用户',
                        dataIndex: 'username',
                        key: 'username',
                        width: 120,
                      },
                      {
                        title: '状态',
                        dataIndex: 'status',
                        key: 'status',
                        width: 80,
                        render: (status: number) => (
                          status === 1 ? (
                            <Tag color="success" icon={<CheckOutlined />}>成功</Tag>
                          ) : (
                            <Tag color="error" icon={<CloseOutlined />}>失败</Tag>
                          )
                        ),
                      },
                      {
                        title: 'IP地址',
                        dataIndex: 'ip_address',
                        key: 'ip_address',
                        width: 140,
                      },
                      {
                        title: '登录方式',
                        dataIndex: 'login_type',
                        key: 'login_type',
                        width: 100,
                        render: (type: string) => (
                          type === '2fa' ? <Tag color="blue">2FA</Tag> : <Tag>密码</Tag>
                        ),
                      },
                      {
                        title: '失败原因',
                        dataIndex: 'failure_reason',
                        key: 'failure_reason',
                        ellipsis: true,
                      },
                      {
                        title: '时间',
                        dataIndex: 'created_at',
                        key: 'created_at',
                        width: 180,
                        render: (time: string) => new Date(time).toLocaleString('zh-CN'),
                      },
                    ]}
                  />
                </Card>
              ),
            },
            {
              key: 'sessions',
              label: <span><ClockCircleOutlined />会话管理</span>,
              children: (
                <Card
                  title={<Space><ClockCircleOutlined />活动会话</Space>}
                  style={{ borderRadius: 10 }}
                  extra={
                    <Space>
                      <Button icon={<ReloadOutlined />} onClick={fetchSessions}>刷新</Button>
                      <Button danger onClick={handleRevokeAllSessions}>撤销所有其他会话</Button>
                    </Space>
                  }
                >
                  <Table
                    dataSource={sessions}
                    rowKey="id"
                    loading={sessionsLoading}
                    scroll={{ y: 400 }}
                    virtual
                    pagination={false}
                    columns={[
                      {
                        title: 'IP地址',
                        dataIndex: 'ip_address',
                        key: 'ip_address',
                        width: 140,
                      },
                      {
                        title: '用户代理',
                        dataIndex: 'user_agent',
                        key: 'user_agent',
                        ellipsis: true,
                      },
                      {
                        title: '最后活动',
                        dataIndex: 'last_activity',
                        key: 'last_activity',
                        width: 180,
                        render: (time: string) => new Date(time).toLocaleString('zh-CN'),
                      },
                      {
                        title: '操作',
                        key: 'actions',
                        width: 100,
                        render: (_: any, record: any) => (
                          <Popconfirm
                            title="确定撤销此会话？"
                            onConfirm={() => handleRevokeSession(record.id)}
                          >
                            <Button type="text" size="small" danger>撤销</Button>
                          </Popconfirm>
                        ),
                      },
                    ]}
                  />
                </Card>
              ),
            },
            {
              key: 'ipWhitelist',
              label: <span><GlobalOutlined />IP白名单</span>,
              children: (
                <Card
                  title={<Space><GlobalOutlined />IP白名单</Space>}
                  style={{ borderRadius: 10 }}
                  extra={
                    <Space>
                      <Button icon={<ReloadOutlined />} onClick={fetchIPWhitelist}>刷新</Button>
                      <Button type="primary" onClick={() => setShowAddIP(true)}>添加IP</Button>
                    </Space>
                  }
                >
                  <Table
                    dataSource={ipWhitelist}
                    rowKey="id"
                    loading={ipWhitelistLoading}
                    scroll={{ y: 400 }}
                    virtual
                    pagination={false}
                    columns={[
                      {
                        title: 'IP地址',
                        dataIndex: 'ip_address',
                        key: 'ip_address',
                        width: 140,
                      },
                      {
                        title: '描述',
                        dataIndex: 'description',
                        key: 'description',
                        ellipsis: true,
                      },
                      {
                        title: '状态',
                        dataIndex: 'enabled',
                        key: 'enabled',
                        width: 100,
                        render: (enabled: boolean, record: any) => (
                          <Switch
                            checked={enabled}
                            onChange={(checked) => handleToggleIP(record.id, checked)}
                          />
                        ),
                      },
                      {
                        title: '创建时间',
                        dataIndex: 'created_at',
                        key: 'created_at',
                        width: 180,
                        render: (time: string) => new Date(time).toLocaleString('zh-CN'),
                      },
                      {
                        title: '操作',
                        key: 'actions',
                        width: 100,
                        render: (_: any, record: any) => (
                          <Popconfirm
                            title="确定删除？"
                            onConfirm={() => handleDeleteIP(record.id)}
                          >
                            <Button type="text" size="small" danger icon={<DeleteOutlined />} />
                          </Popconfirm>
                        ),
                      },
                    ]}
                  />

                  <Modal
                    title="添加IP白名单"
                    open={showAddIP}
                    onOk={handleAddIP}
                    onCancel={() => {
                      setShowAddIP(false)
                      ipForm.resetFields()
                    }}
                  >
                    <Form form={ipForm} layout="vertical">
                      <Form.Item
                        name="ip_address"
                        label="IP地址"
                        rules={[{ required: true, message: '请输入IP地址' }]}
                      >
                        <Input placeholder="例如: 192.168.1.1" />
                      </Form.Item>
                      <Form.Item name="description" label="描述">
                        <Input.TextArea placeholder="备注信息" rows={3} />
                      </Form.Item>
                    </Form>
                  </Modal>
                </Card>
              ),
            },
          ]}
        />
      ),
    },
  ]

  return (
    <div className="animate-fade-in">
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <Title level={4} style={{ margin: 0, fontWeight: 600 }}>系统设置</Title>
        <Button icon={<ReloadOutlined />} onClick={() => { fetchData(); fetchConfigs() }} loading={loading}>刷新</Button>
      </div>

      <Tabs items={tabItems} />
    </div>
  )
}
