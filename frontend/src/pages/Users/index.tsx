import { useEffect, useState } from 'react'
import {
  Card, Table, Button, Space, Modal, Form, Input,
  Select, Switch, Typography, message, Popconfirm,
  Tag, Tooltip,
} from 'antd'
import {
  PlusOutlined, ReloadOutlined, DeleteOutlined,
  EditOutlined, UserOutlined,
} from '@ant-design/icons'
import { userApi } from '../../services/api'
import { useAuthStore } from '../../stores/authStore'
import dayjs from 'dayjs'
import { formatUTCTime } from '../../utils/timeHelper'

const { Title, Text } = Typography

const ROLE_OPTIONS = [
  { label: '管理员', value: 'admin' },
  { label: '操作员', value: 'operator' },
  { label: '观察者', value: 'viewer' },
]

const ROLE_MAP: Record<string, { text: string; color: string }> = {
  admin: { text: '管理员', color: 'red' },
  operator: { text: '操作员', color: 'blue' },
  viewer: { text: '观察者', color: 'default' },
}

interface UserRecord {
  id: number
  username: string
  role: string
  enabled: boolean
  last_login_at: string | null
  created_at: string
}

export default function Users() {
  const [users, setUsers] = useState<UserRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingUser, setEditingUser] = useState<UserRecord | null>(null)
  const [form] = Form.useForm()
  const currentUser = useAuthStore((s) => s.user)

  useEffect(() => {
    fetchUsers()
  }, [])

  const fetchUsers = async () => {
    setLoading(true)
    try {
      const res = await userApi.list()
      setUsers(res.data.data || [])
    } catch (err: any) {
      if (err?.response?.status === 403) {
        message.error('权限不足，仅管理员可访问')
      } else {
        message.error('获取用户列表失败')
      }
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = () => {
    setEditingUser(null)
    form.resetFields()
    form.setFieldsValue({ role: 'viewer' })
    setModalOpen(true)
  }

  const handleEdit = (record: UserRecord) => {
    setEditingUser(record)
    form.setFieldsValue({
      username: record.username,
      role: record.role,
    })
    setModalOpen(true)
  }

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      if (editingUser) {
        const payload: Record<string, any> = {}
        if (values.username !== editingUser.username) payload.username = values.username
        if (values.role !== editingUser.role) payload.role = values.role
        if (values.password) payload.password = values.password
        await userApi.update(editingUser.id, payload)
        message.success('更新成功')
      } else {
        await userApi.create(values)
        message.success('创建成功')
      }
      setModalOpen(false)
      fetchUsers()
    } catch (err: any) {
      if (err?.response?.data?.error) {
        message.error(err.response.data.error)
      }
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await userApi.delete(id)
      message.success('删除成功')
      fetchUsers()
    } catch (err: any) {
      message.error(err?.response?.data?.error || '删除失败')
    }
  }

  const handleToggle = async (record: UserRecord) => {
    try {
      await userApi.update(record.id, { enabled: !record.enabled })
      message.success(record.enabled ? '已禁用' : '已启用')
      fetchUsers()
    } catch (err: any) {
      message.error(err?.response?.data?.error || '操作失败')
    }
  }

  const isSelf = (record: UserRecord) => currentUser?.username === record.username

  const columns = [
    {
      title: '用户名',
      dataIndex: 'username',
      key: 'username',
      width: 160,
      render: (v: string, record: UserRecord) => (
        <Space>
          <UserOutlined style={{ color: '#1677FF' }} />
          <Text strong={isSelf(record)}>{v}</Text>
          {isSelf(record) && <Tag color="green">当前</Tag>}
        </Space>
      ),
    },
    {
      title: '角色',
      dataIndex: 'role',
      key: 'role',
      width: 100,
      render: (v: string) => {
        const info = ROLE_MAP[v] || { text: v, color: 'default' }
        return <Tag color={info.color}>{info.text}</Tag>
      },
    },
    {
      title: '状态',
      dataIndex: 'enabled',
      key: 'enabled',
      width: 80,
      render: (enabled: boolean, record: UserRecord) => (
        <Switch
          size="small"
          checked={enabled}
          disabled={isSelf(record)}
          onChange={() => handleToggle(record)}
        />
      ),
    },
    {
      title: '最后登录',
      dataIndex: 'last_login_at',
      key: 'last_login_at',
      width: 160,
      render: (v: string | null) => {
        const formatted = formatUTCTime(v, 'YYYY-MM-DD HH:mm')
        return formatted === '-' ? <Text type="secondary">未登录</Text> : formatted
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (v: string) => formatUTCTime(v, 'YYYY-MM-DD HH:mm'),
    },
    {
      title: '操作',
      key: 'actions',
      width: 120,
      render: (_: any, record: UserRecord) => (
        <Space size={4}>
          <Tooltip title="编辑">
            <Button type="text" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)} />
          </Tooltip>
          {!isSelf(record) && (
            <Popconfirm title="确定删除该用户？" onConfirm={() => handleDelete(record.id)}>
              <Tooltip title="删除">
                <Button type="text" size="small" icon={<DeleteOutlined />} danger />
              </Tooltip>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div className="animate-fade-in">
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <Title level={4} style={{ margin: 0, fontWeight: 600 }}>用户管理</Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={fetchUsers}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>新建用户</Button>
        </Space>
      </div>

      <Card style={{ borderRadius: 10 }} styles={{ body: { padding: 0 } }}>
        <Table
          dataSource={users}
          columns={columns}
          rowKey="id"
          loading={loading}
          size="middle"
          scroll={{ y: 600 }}
          virtual
          pagination={false}
          locale={{ emptyText: '暂无用户' }}
        />
      </Card>

      <Modal
        title={editingUser ? '编辑用户' : '新建用户'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        okText="保存"
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="username"
            label="用户名"
            rules={[
              { required: true, message: '请输入用户名' },
              { min: 3, message: '至少 3 个字符' },
            ]}
          >
            <Input placeholder="用户名" />
          </Form.Item>
          <Form.Item
            name="password"
            label={editingUser ? '新密码（留空不修改）' : '密码'}
            rules={editingUser ? [] : [
              { required: true, message: '请输入密码' },
              { min: 8, message: '至少 8 个字符' },
            ]}
          >
            <Input.Password placeholder={editingUser ? '留空则不修改' : '至少 8 个字符'} />
          </Form.Item>
          <Form.Item name="role" label="角色" rules={[{ required: true, message: '请选择角色' }]}>
            <Select options={ROLE_OPTIONS} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
