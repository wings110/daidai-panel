import { useEffect, useState } from 'react'
import {
  Card, Table, Button, Space, Modal, Form, Input,
  Switch, Typography, message, Popconfirm, Tag, Tooltip,
} from 'antd'
import {
  PlusOutlined, ReloadOutlined, DeleteOutlined,
  EditOutlined, CloudDownloadOutlined, CheckCircleOutlined,
  CloseCircleOutlined, MinusCircleOutlined,
} from '@ant-design/icons'
import { subApi } from '../../services/api'
import dayjs from 'dayjs'
import { formatUTCTime } from '../../utils/timeHelper'

const { Title, Text } = Typography

interface SubRecord {
  id: number
  name: string
  url: string
  branch: string
  schedule: string
  whitelist: string
  blacklist: string
  target_dir: string
  enabled: boolean
  last_pull_at: string | null
  last_pull_status: number
  last_pull_message: string
  created_at: string
}

export default function Subscriptions() {
  const [subs, setSubs] = useState<SubRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingSub, setEditingSub] = useState<SubRecord | null>(null)
  const [pulling, setPulling] = useState<number | null>(null)
  const [form] = Form.useForm()

  useEffect(() => {
    fetchSubs()
  }, [])

  const fetchSubs = async () => {
    setLoading(true)
    try {
      const res = await subApi.list()
      setSubs(res.data.data || [])
    } catch {
      message.error('获取订阅列表失败')
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = () => {
    setEditingSub(null)
    form.resetFields()
    form.setFieldsValue({ branch: 'main', schedule: '0 0 * * *' })
    setModalOpen(true)
  }

  const handleEdit = (record: SubRecord) => {
    setEditingSub(record)
    form.setFieldsValue(record)
    setModalOpen(true)
  }

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      if (editingSub) {
        await subApi.update(editingSub.id, values)
        message.success('更新成功')
      } else {
        await subApi.create(values)
        message.success('创建成功')
      }
      setModalOpen(false)
      fetchSubs()
    } catch (err: any) {
      if (err?.response?.data?.error) {
        message.error(err.response.data.error)
      }
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await subApi.delete(id)
      message.success('删除成功')
      fetchSubs()
    } catch {
      message.error('删除失败')
    }
  }

  const handlePull = async (id: number) => {
    setPulling(id)
    try {
      const res = await subApi.pull(id)
      message.success(res.data.message || '拉取完成')
      fetchSubs()
    } catch (err: any) {
      message.error(err?.response?.data?.error || '拉取失败')
    } finally {
      setPulling(null)
    }
  }

  const handleToggle = async (record: SubRecord) => {
    try {
      await subApi.update(record.id, { enabled: !record.enabled })
      message.success(record.enabled ? '已禁用' : '已启用')
      fetchSubs()
    } catch {
      message.error('操作失败')
    }
  }

  const pullStatusTag = (status: number) => {
    if (status === -1) return <Tag icon={<MinusCircleOutlined />} color="default">未执行</Tag>
    if (status === 0) return <Tag icon={<CheckCircleOutlined />} color="success">成功</Tag>
    return <Tag icon={<CloseCircleOutlined />} color="error">失败</Tag>
  }

  const columns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      width: 140,
    },
    {
      title: '仓库地址',
      dataIndex: 'url',
      key: 'url',
      ellipsis: true,
      render: (v: string) => (
        <Tooltip title={v}>
          <Text copyable={{ text: v }} style={{ fontSize: 12 }}>{v}</Text>
        </Tooltip>
      ),
    },
    {
      title: '分支',
      dataIndex: 'branch',
      key: 'branch',
      width: 80,
      render: (v: string) => <Tag>{v}</Tag>,
    },
    {
      title: 'Cron',
      dataIndex: 'schedule',
      key: 'schedule',
      width: 120,
      render: (v: string) => <code style={{ fontSize: 12 }}>{v}</code>,
    },
    {
      title: '上次拉取',
      key: 'last_pull',
      width: 160,
      render: (_: any, r: SubRecord) => (
        <Space direction="vertical" size={0}>
          {pullStatusTag(r.last_pull_status)}
          {r.last_pull_at && (
            <Text type="secondary" style={{ fontSize: 11 }}>
              {formatUTCTime(r.last_pull_at, 'MM-DD HH:mm')}
            </Text>
          )}
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'enabled',
      key: 'enabled',
      width: 70,
      render: (enabled: boolean, record: SubRecord) => (
        <Switch size="small" checked={enabled} onChange={() => handleToggle(record)} />
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 160,
      render: (_: any, record: SubRecord) => (
        <Space size={4}>
          <Tooltip title="立即拉取">
            <Button
              type="text" size="small"
              icon={<CloudDownloadOutlined />}
              loading={pulling === record.id}
              onClick={() => handlePull(record.id)}
            />
          </Tooltip>
          <Tooltip title="编辑">
            <Button type="text" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)} />
          </Tooltip>
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
        <Title level={4} style={{ margin: 0, fontWeight: 600 }}>订阅管理</Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={fetchSubs}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>新建订阅</Button>
        </Space>
      </div>

      <Card style={{ borderRadius: 10 }} styles={{ body: { padding: 0 } }}>
        <Table
          dataSource={subs}
          columns={columns}
          rowKey="id"
          loading={loading}
          size="middle"
          scroll={{ y: 600 }}
          virtual
          pagination={false}
          locale={{ emptyText: '暂无订阅' }}
        />
      </Card>

      <Modal
        title={editingSub ? '编辑订阅' : '新建订阅'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        okText="保存"
        width={560}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="例如：我的签到脚本集" />
          </Form.Item>
          <Form.Item
            name="url"
            label="仓库地址"
            rules={[
              { required: true, message: '请输入仓库地址' },
              { type: 'url', message: '请输入有效的 URL' },
            ]}
          >
            <Input placeholder="https://github.com/user/repo.git" />
          </Form.Item>
          <Space style={{ width: '100%' }} size={16}>
            <Form.Item name="branch" label="分支" style={{ width: 200 }}>
              <Input placeholder="main" />
            </Form.Item>
            <Form.Item name="schedule" label="定时 Cron" style={{ width: 200 }}>
              <Input placeholder="0 0 * * *" />
            </Form.Item>
          </Space>
          <Form.Item name="whitelist" label="白名单（glob，逗号分隔）">
            <Input placeholder="*.py,*.js（留空则拉取全部）" />
          </Form.Item>
          <Form.Item name="blacklist" label="黑名单（glob，逗号分隔）">
            <Input placeholder="*.md,LICENSE" />
          </Form.Item>
          <Form.Item name="target_dir" label="存放子目录">
            <Input placeholder="留空则放在脚本根目录" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
