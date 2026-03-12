import { useEffect, useState } from 'react'
import {
  Card, Table, Button, Space, Modal, Form, Input,
  Select, Switch, Typography, message, Popconfirm,
  Tag, Tooltip, InputNumber, Alert,
} from 'antd'
import {
  PlusOutlined, ReloadOutlined, DeleteOutlined,
  EditOutlined, CopyOutlined, SyncOutlined, EyeOutlined, EyeInvisibleOutlined,
} from '@ant-design/icons'
import { openApiApi } from '../../services/api'

const { Title, Text, Paragraph } = Typography

const SCOPE_OPTIONS = [
  { label: '任务管理', value: 'tasks' },
  { label: '脚本管理', value: 'scripts' },
  { label: '环境变量', value: 'envs' },
  { label: '日志查看', value: 'logs' },
  { label: '系统信息', value: 'system' },
]

interface AppRecord {
  id: number
  name: string
  client_id: string
  client_secret?: string
  scopes: string[]
  token_expiry: number
  enabled: boolean
  last_used_at: string | null
  created_at: string
}

export default function OpenApi() {
  const [apps, setApps] = useState<AppRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingApp, setEditingApp] = useState<AppRecord | null>(null)
  const [createdSecret, setCreatedSecret] = useState<{ clientId: string; clientSecret: string } | null>(null)
  const [form] = Form.useForm()
  const [visibleSecrets, setVisibleSecrets] = useState<Record<number, string>>({})
  const [loadingSecrets, setLoadingSecrets] = useState<Record<number, boolean>>({})

  useEffect(() => {
    fetchApps()
  }, [])

  const fetchApps = async () => {
    setLoading(true)
    try {
      const res = await openApiApi.listApps()
      setApps(res.data.data || [])
    } catch {
      message.error('获取应用列表失败')
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = () => {
    setEditingApp(null)
    form.resetFields()
    form.setFieldsValue({ token_expiry: 2592000, scopes: [] })
    setModalOpen(true)
  }

  const handleEdit = (record: AppRecord) => {
    setEditingApp(record)
    form.setFieldsValue(record)
    setModalOpen(true)
  }

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      if (editingApp) {
        await openApiApi.updateApp(editingApp.id, values)
        message.success('更新成功')
        setModalOpen(false)
      } else {
        const res = await openApiApi.createApp(values)
        const data = res.data.data
        setCreatedSecret({
          clientId: data.client_id,
          clientSecret: data.client_secret,
        })
        setModalOpen(false)
      }
      fetchApps()
    } catch (err: any) {
      if (err?.response?.data?.error) {
        message.error(err.response.data.error)
      }
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await openApiApi.deleteApp(id)
      message.success('删除成功')
      fetchApps()
    } catch {
      message.error('删除失败')
    }
  }

  const handleResetSecret = async (id: number) => {
    try {
      const res = await openApiApi.resetSecret(id)
      const app = apps.find((a) => a.id === id)
      setCreatedSecret({
        clientId: app?.client_id || '',
        clientSecret: res.data.client_secret,
      })
      // 清除该应用的可见状态
      setVisibleSecrets(prev => {
        const next = { ...prev }
        delete next[id]
        return next
      })
      message.success('Secret 已重置')
    } catch {
      message.error('重置失败')
    }
  }

  const handleToggle = async (record: AppRecord) => {
    try {
      await openApiApi.updateApp(record.id, { enabled: !record.enabled })
      message.success(record.enabled ? '已禁用' : '已启用')
      fetchApps()
    } catch {
      message.error('操作失败')
    }
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
    message.success('已复制到剪贴板')
  }

  const handleToggleSecret = async (id: number) => {
    if (visibleSecrets[id]) {
      // 隐藏
      setVisibleSecrets(prev => {
        const next = { ...prev }
        delete next[id]
        return next
      })
    } else {
      // 弹窗输入密码进行二次验证
      let passwordValue = ''
      Modal.confirm({
        title: '安全验证',
        content: (
          <div>
            <p style={{ marginBottom: 8, color: '#666' }}>查看 Client Secret 需要验证当前登录密码</p>
            <Input.Password
              placeholder="请输入当前登录密码"
              onChange={e => { passwordValue = e.target.value }}
              onPressEnter={() => {
                // Enter 键触发确认
                const btn = document.querySelector('.ant-modal-confirm-btns .ant-btn-primary') as HTMLElement
                btn?.click()
              }}
            />
          </div>
        ),
        okText: '验证',
        cancelText: '取消',
        onOk: async () => {
          if (!passwordValue) {
            message.warning('请输入密码')
            throw new Error('密码为空')
          }
          setLoadingSecrets(prev => ({ ...prev, [id]: true }))
          try {
            const res = await openApiApi.getSecret(id, passwordValue)
            setVisibleSecrets(prev => ({ ...prev, [id]: res.data.client_secret }))
          } catch (err: any) {
            const errMsg = err?.response?.data?.error || '获取 Secret 失败'
            message.error(errMsg)
            throw err
          } finally {
            setLoadingSecrets(prev => ({ ...prev, [id]: false }))
          }
        },
      })
    }
  }

  const columns = [
    {
      title: '应用名称',
      dataIndex: 'name',
      key: 'name',
      width: 160,
    },
    {
      title: 'Client ID',
      dataIndex: 'client_id',
      key: 'client_id',
      width: 280,
      render: (v: string) => (
        <Space>
          <code style={{ fontSize: 12 }}>{v}</code>
          <Tooltip title="复制">
            <Button type="text" size="small" icon={<CopyOutlined />} onClick={() => copyToClipboard(v)} />
          </Tooltip>
        </Space>
      ),
    },
    {
      title: 'Client Secret',
      key: 'client_secret',
      width: 320,
      render: (_: any, record: AppRecord) => {
        const isVisible = !!visibleSecrets[record.id]
        const isLoading = !!loadingSecrets[record.id]
        return (
          <Space>
            <code style={{ fontSize: 12 }}>
              {isVisible ? visibleSecrets[record.id] : '••••••••••••••••'}
            </code>
            <Tooltip title={isVisible ? '隐藏' : '显示'}>
              <Button
                type="text"
                size="small"
                icon={isVisible ? <EyeInvisibleOutlined /> : <EyeOutlined />}
                loading={isLoading}
                onClick={() => handleToggleSecret(record.id)}
              />
            </Tooltip>
            {isVisible && (
              <Tooltip title="复制">
                <Button
                  type="text"
                  size="small"
                  icon={<CopyOutlined />}
                  onClick={() => copyToClipboard(visibleSecrets[record.id])}
                />
              </Tooltip>
            )}
          </Space>
        )
      },
    },
    {
      title: '权限',
      dataIndex: 'scopes',
      key: 'scopes',
      width: 200,
      render: (scopes: string[]) => (
        <Space wrap size={4}>
          {scopes.length === 0 ? (
            <Tag>全部权限</Tag>
          ) : (
            scopes.map((s) => <Tag key={s} color="blue">{s}</Tag>)
          )}
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'enabled',
      key: 'enabled',
      width: 80,
      render: (enabled: boolean, record: AppRecord) => (
        <Switch size="small" checked={enabled} onChange={() => handleToggle(record)} />
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 180,
      render: (_: any, record: AppRecord) => (
        <Space size={4}>
          <Tooltip title="编辑">
            <Button type="text" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)} />
          </Tooltip>
          <Popconfirm title="重置 Secret 后旧 Secret 将失效，确定？" onConfirm={() => handleResetSecret(record.id)}>
            <Tooltip title="重置 Secret">
              <Button type="text" size="small" icon={<SyncOutlined />} />
            </Tooltip>
          </Popconfirm>
          <Popconfirm title="确定删除？" onConfirm={() => handleDelete(record.id)}>
            <Tooltip title="删除">
              <Button type="text" size="small" icon={<DeleteOutlined />} danger />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div className="animate-fade-in">
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <Title level={4} style={{ margin: 0, fontWeight: 600 }}>开放 API</Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={fetchApps}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>新建应用</Button>
        </Space>
      </div>

      <Card style={{ borderRadius: 10 }} styles={{ body: { padding: 0 } }}>
        <Table
          dataSource={apps}
          columns={columns}
          rowKey="id"
          loading={loading}
          size="middle"
          scroll={{ y: 600 }}
          virtual
          pagination={false}
          locale={{ emptyText: '暂无应用' }}
        />
      </Card>

      {/* 创建/编辑弹窗 */}
      <Modal
        title={editingApp ? '编辑应用' : '新建应用'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        okText="保存"
        cancelText="取消"
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="name"
            label="应用名称"
            rules={[{ required: true, message: '请输入应用名称' }]}
          >
            <Input placeholder="例如：外部调度系统" />
          </Form.Item>
          <Form.Item name="scopes" label="权限范围">
            <Select
              mode="multiple"
              placeholder="留空表示全部权限"
              options={SCOPE_OPTIONS}
              allowClear
            />
          </Form.Item>
          <Form.Item
            name="token_expiry"
            label="Access Token 有效期（秒）"
            tooltip="每次获取的 Access Token 的有效期，过期后需重新获取。Client Secret 永久有效。"
          >
            <InputNumber
              min={3600}
              max={31536000}
              style={{ width: '100%' }}
              placeholder="默认 2592000 秒（30天）"
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* Secret 展示弹窗 */}
      <Modal
        title="应用凭证"
        open={!!createdSecret}
        onCancel={() => setCreatedSecret(null)}
        footer={[
          <Button key="ok" type="primary" onClick={() => setCreatedSecret(null)}>
            我已保存
          </Button>,
        ]}
      >
        <Alert
          type="warning"
          message="请妥善保管 Client Secret，关闭后将无法再次查看"
          style={{ marginBottom: 16 }}
        />
        {createdSecret && (
          <div>
            <div style={{ marginBottom: 12 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>Client ID</Text>
              <Paragraph
                copyable
                code
                style={{ fontSize: 13, marginBottom: 0, marginTop: 4 }}
              >
                {createdSecret.clientId}
              </Paragraph>
            </div>
            <div>
              <Text type="secondary" style={{ fontSize: 12 }}>Client Secret</Text>
              <Paragraph
                copyable
                code
                style={{ fontSize: 13, marginBottom: 0, marginTop: 4 }}
              >
                {createdSecret.clientSecret}
              </Paragraph>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
