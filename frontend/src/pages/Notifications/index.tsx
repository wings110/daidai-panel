import { useEffect, useState } from 'react'
import {
  Card, Table, Button, Space, Modal, Form, Input,
  Select, Switch, Typography, message, Popconfirm,
  Tag, Tooltip, InputNumber, Descriptions,
} from 'antd'
import {
  PlusOutlined, ReloadOutlined, DeleteOutlined,
  EditOutlined, SendOutlined, BellOutlined,
} from '@ant-design/icons'
import { notifyApi } from '../../services/api'

const { Title, Text } = Typography

const TYPE_OPTIONS = [
  { label: 'WebHook', value: 'webhook' },
  { label: '邮件', value: 'email' },
  { label: 'Telegram', value: 'telegram' },
  { label: '钉钉机器人', value: 'dingtalk' },
  { label: '企业微信', value: 'wecom' },
  { label: 'Bark (iOS)', value: 'bark' },
  { label: 'PushPlus', value: 'pushplus' },
  { label: 'Server 酱', value: 'serverchan' },
  { label: '飞书机器人', value: 'feishu' },
]

const TYPE_LABELS: Record<string, { text: string; color: string }> = {
  webhook: { text: 'WebHook', color: 'blue' },
  email: { text: '邮件', color: 'green' },
  telegram: { text: 'Telegram', color: 'cyan' },
  dingtalk: { text: '钉钉', color: 'geekblue' },
  wecom: { text: '企业微信', color: 'lime' },
  bark: { text: 'Bark', color: 'orange' },
  pushplus: { text: 'PushPlus', color: 'purple' },
  serverchan: { text: 'Server酱', color: 'magenta' },
  feishu: { text: '飞书', color: 'volcano' },
}

interface ChannelRecord {
  id: number
  name: string
  type: string
  config: Record<string, any>
  enabled: boolean
  created_at: string
}

export default function Notifications() {
  const [channels, setChannels] = useState<ChannelRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingChannel, setEditingChannel] = useState<ChannelRecord | null>(null)
  const [testing, setTesting] = useState<number | null>(null)
  const [form] = Form.useForm()
  const selectedType = Form.useWatch('type', form)

  useEffect(() => {
    fetchChannels()
  }, [])

  const fetchChannels = async () => {
    setLoading(true)
    try {
      const res = await notifyApi.list()
      setChannels(res.data.data || [])
    } catch {
      message.error('获取通知渠道失败')
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = () => {
    setEditingChannel(null)
    form.resetFields()
    setModalOpen(true)
  }

  const handleEdit = (record: ChannelRecord) => {
    setEditingChannel(record)
    form.setFieldsValue({
      name: record.name,
      type: record.type,
      ...flattenConfig(record.type, record.config),
    })
    setModalOpen(true)
  }

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      const { name, type, ...configFields } = values
      const config = buildConfig(type, configFields)

      if (editingChannel) {
        await notifyApi.update(editingChannel.id, { name, type, config })
        message.success('更新成功')
      } else {
        await notifyApi.create({ name, type, config })
        message.success('创建成功')
      }
      setModalOpen(false)
      fetchChannels()
    } catch (err: any) {
      if (err?.response?.data?.error) {
        message.error(err.response.data.error)
      }
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await notifyApi.delete(id)
      message.success('删除成功')
      fetchChannels()
    } catch {
      message.error('删除失败')
    }
  }

  const handleTest = async (id: number) => {
    setTesting(id)
    try {
      await notifyApi.test(id)
      message.success('测试通知发送成功')
    } catch (err: any) {
      message.error(err?.response?.data?.error || '测试发送失败')
    } finally {
      setTesting(null)
    }
  }

  const handleToggle = async (record: ChannelRecord) => {
    try {
      await notifyApi.update(record.id, { enabled: !record.enabled })
      message.success(record.enabled ? '已禁用' : '已启用')
      fetchChannels()
    } catch {
      message.error('操作失败')
    }
  }

  const flattenConfig = (type: string, config: Record<string, any>) => {
    const result: Record<string, any> = {}
    if (type === 'webhook') {
      result.webhook_url = config.url || ''
      result.webhook_method = config.method || 'POST'
    } else if (type === 'email') {
      result.smtp_host = config.smtp_host || ''
      result.smtp_port = config.smtp_port || 465
      result.email_username = config.username || ''
      result.email_password = config.password || ''
      result.email_to = config.to || ''
    } else if (type === 'telegram') {
      result.bot_token = config.bot_token || ''
      result.chat_id = config.chat_id || ''
      result.tg_api_host = config.api_host || ''
    } else if (type === 'dingtalk') {
      result.dd_token = config.token || ''
      result.dd_secret = config.secret || ''
    } else if (type === 'wecom') {
      result.wecom_key = config.key || ''
    } else if (type === 'bark') {
      result.bark_server = config.server || 'https://api.day.app'
      result.bark_device_key = config.device_key || ''
      result.bark_sound = config.sound || ''
      result.bark_group = config.group || '呆呆面板'
    } else if (type === 'pushplus') {
      result.pp_token = config.token || ''
      result.pp_topic = config.topic || ''
      result.pp_channel = config.channel || 'wechat'
      result.pp_template = config.template || 'html'
    } else if (type === 'serverchan') {
      result.sc_send_key = config.send_key || ''
    } else if (type === 'feishu') {
      result.fs_webhook = config.webhook || ''
      result.fs_secret = config.secret || ''
    }
    return result
  }

  const buildConfig = (type: string, fields: Record<string, any>) => {
    if (type === 'webhook') {
      return { url: fields.webhook_url, method: fields.webhook_method || 'POST' }
    } else if (type === 'email') {
      return {
        smtp_host: fields.smtp_host,
        smtp_port: fields.smtp_port,
        username: fields.email_username,
        password: fields.email_password,
        to: fields.email_to,
      }
    } else if (type === 'telegram') {
      return { bot_token: fields.bot_token, chat_id: fields.chat_id, api_host: fields.tg_api_host || '' }
    } else if (type === 'dingtalk') {
      return { token: fields.dd_token, secret: fields.dd_secret || '' }
    } else if (type === 'wecom') {
      return { key: fields.wecom_key }
    } else if (type === 'bark') {
      return {
        server: fields.bark_server || 'https://api.day.app',
        device_key: fields.bark_device_key,
        sound: fields.bark_sound || '',
        group: fields.bark_group || '呆呆面板',
      }
    } else if (type === 'pushplus') {
      return {
        token: fields.pp_token,
        topic: fields.pp_topic || '',
        channel: fields.pp_channel || 'wechat',
        template: fields.pp_template || 'html',
      }
    } else if (type === 'serverchan') {
      return { send_key: fields.sc_send_key }
    } else if (type === 'feishu') {
      return { webhook: fields.fs_webhook, secret: fields.fs_secret || '' }
    }
    return {}
  }

  const columns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      width: 160,
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: 100,
      render: (v: string) => {
        const info = TYPE_LABELS[v] || { text: v, color: 'default' }
        return <Tag color={info.color}>{info.text}</Tag>
      },
    },
    {
      title: '配置摘要',
      key: 'config_summary',
      ellipsis: true,
      render: (_: any, r: ChannelRecord) => {
        if (r.type === 'webhook') return <Text type="secondary">{r.config.url}</Text>
        if (r.type === 'email') return <Text type="secondary">{r.config.to}</Text>
        if (r.type === 'telegram') return <Text type="secondary">Chat: {r.config.chat_id}</Text>
        if (r.type === 'dingtalk') return <Text type="secondary">Token: {(r.config.token || '').slice(0, 12)}...</Text>
        if (r.type === 'wecom') return <Text type="secondary">Key: {(r.config.key || '').slice(0, 12)}...</Text>
        if (r.type === 'bark') return <Text type="secondary">{r.config.server || 'api.day.app'}</Text>
        if (r.type === 'pushplus') return <Text type="secondary">Token: {(r.config.token || '').slice(0, 12)}...</Text>
        if (r.type === 'serverchan') return <Text type="secondary">Key: {(r.config.send_key || '').slice(0, 12)}...</Text>
        if (r.type === 'feishu') return <Text type="secondary">Webhook 已配置</Text>
        return '-'
      },
    },
    {
      title: '状态',
      dataIndex: 'enabled',
      key: 'enabled',
      width: 70,
      render: (enabled: boolean, record: ChannelRecord) => (
        <Switch size="small" checked={enabled} onChange={() => handleToggle(record)} />
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 160,
      render: (_: any, record: ChannelRecord) => (
        <Space size={4}>
          <Tooltip title="测试发送">
            <Button
              type="text" size="small"
              icon={<SendOutlined />}
              loading={testing === record.id}
              onClick={() => handleTest(record.id)}
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
        <Title level={4} style={{ margin: 0, fontWeight: 600 }}>
          <Space><BellOutlined />通知设置</Space>
        </Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={fetchChannels}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>新建渠道</Button>
        </Space>
      </div>

      <Card style={{ borderRadius: 10 }} styles={{ body: { padding: 0 } }}>
        <Table
          dataSource={channels}
          columns={columns}
          rowKey="id"
          loading={loading}
          size="middle"
          scroll={{ y: 600 }}
          virtual
          pagination={false}
          locale={{ emptyText: '暂无通知渠道，任务失败时将无法发送通知' }}
        />
      </Card>

      <Modal
        title={editingChannel ? '编辑渠道' : '新建渠道'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        okText="保存"
        width={520}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="例如：企业微信通知" />
          </Form.Item>
          <Form.Item name="type" label="类型" rules={[{ required: true, message: '请选择类型' }]}>
            <Select placeholder="选择通知类型" options={TYPE_OPTIONS} />
          </Form.Item>

          {/* WebHook 配置 */}
          {selectedType === 'webhook' && (
            <>
              <Form.Item name="webhook_url" label="WebHook URL" rules={[{ required: true, message: '请输入 URL' }]}>
                <Input placeholder="https://..." />
              </Form.Item>
              <Form.Item name="webhook_method" label="请求方法" initialValue="POST">
                <Select options={[{ label: 'POST', value: 'POST' }, { label: 'GET', value: 'GET' }]} />
              </Form.Item>
            </>
          )}

          {/* 邮件配置 */}
          {selectedType === 'email' && (
            <>
              <Space style={{ width: '100%' }} size={16}>
                <Form.Item name="smtp_host" label="SMTP 主机" rules={[{ required: true }]} style={{ flex: 1 }}>
                  <Input placeholder="smtp.qq.com" />
                </Form.Item>
                <Form.Item name="smtp_port" label="端口" rules={[{ required: true }]} style={{ width: 100 }}>
                  <InputNumber placeholder="465" style={{ width: '100%' }} />
                </Form.Item>
              </Space>
              <Form.Item name="email_username" label="用户名" rules={[{ required: true }]}>
                <Input placeholder="your@email.com" />
              </Form.Item>
              <Form.Item name="email_password" label="密码/授权码" rules={[{ required: true }]}>
                <Input.Password placeholder="SMTP 授权码" />
              </Form.Item>
              <Form.Item name="email_to" label="收件人" rules={[{ required: true }]}>
                <Input placeholder="to@email.com（多个用逗号分隔）" />
              </Form.Item>
            </>
          )}

          {/* Telegram 配置 */}
          {selectedType === 'telegram' && (
            <>
              <Form.Item name="bot_token" label="Bot Token" rules={[{ required: true }]}>
                <Input.Password placeholder="从 @BotFather 获取" />
              </Form.Item>
              <Form.Item name="chat_id" label="Chat ID" rules={[{ required: true }]}>
                <Input placeholder="用户或群组 ID" />
              </Form.Item>
              <Form.Item name="tg_api_host" label="API 反代地址" extra="留空使用官方 api.telegram.org">
                <Input placeholder="api.telegram.org" />
              </Form.Item>
            </>
          )}

          {/* 钉钉机器人配置 */}
          {selectedType === 'dingtalk' && (
            <>
              <Form.Item name="dd_token" label="Access Token" rules={[{ required: true }]} extra="Webhook URL 中 access_token= 后面的值">
                <Input.Password placeholder="access_token" />
              </Form.Item>
              <Form.Item name="dd_secret" label="加签密钥" extra="安全设置为加签时必填">
                <Input.Password placeholder="SEC 开头的密钥（可选）" />
              </Form.Item>
            </>
          )}

          {/* 企业微信配置 */}
          {selectedType === 'wecom' && (
            <Form.Item name="wecom_key" label="Webhook Key" rules={[{ required: true }]} extra="Webhook URL 中 key= 后面的值">
              <Input.Password placeholder="webhook key" />
            </Form.Item>
          )}

          {/* Bark 配置 */}
          {selectedType === 'bark' && (
            <>
              <Form.Item name="bark_device_key" label="Device Key" rules={[{ required: true }]} extra="Bark App 中获取的推送密钥">
                <Input.Password placeholder="设备推送 Key" />
              </Form.Item>
              <Form.Item name="bark_server" label="服务器地址" extra="留空使用官方 https://api.day.app">
                <Input placeholder="https://api.day.app" />
              </Form.Item>
              <Form.Item name="bark_group" label="消息分组">
                <Input placeholder="呆呆面板" />
              </Form.Item>
              <Form.Item name="bark_sound" label="推送铃声" extra="留空使用默认铃声">
                <Input placeholder="如 choo" />
              </Form.Item>
            </>
          )}

          {/* PushPlus 配置 */}
          {selectedType === 'pushplus' && (
            <>
              <Form.Item name="pp_token" label="Token" rules={[{ required: true }]} extra="pushplus.plus 登录后获取">
                <Input.Password placeholder="PushPlus Token" />
              </Form.Item>
              <Form.Item name="pp_topic" label="群组编码" extra="一对多推送时填写，留空为一对一">
                <Input placeholder="可选" />
              </Form.Item>
              <Form.Item name="pp_channel" label="推送渠道" initialValue="wechat">
                <Select options={[
                  { label: '微信公众号', value: 'wechat' },
                  { label: '企业微信', value: 'cp' },
                  { label: '邮件', value: 'mail' },
                  { label: 'WebHook', value: 'webhook' },
                ]} />
              </Form.Item>
              <Form.Item name="pp_template" label="消息模板" initialValue="html">
                <Select options={[
                  { label: 'HTML', value: 'html' },
                  { label: '纯文本', value: 'txt' },
                  { label: 'Markdown', value: 'markdown' },
                  { label: 'JSON', value: 'json' },
                ]} />
              </Form.Item>
            </>
          )}

          {/* Server 酱配置 */}
          {selectedType === 'serverchan' && (
            <Form.Item name="sc_send_key" label="SendKey" rules={[{ required: true }]} extra="sct.ftqq.com 登录后获取">
              <Input.Password placeholder="SCT 开头的 SendKey" />
            </Form.Item>
          )}

          {/* 飞书机器人配置 */}
          {selectedType === 'feishu' && (
            <>
              <Form.Item name="fs_webhook" label="Webhook 地址" rules={[{ required: true }]}>
                <Input placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/xxx" />
              </Form.Item>
              <Form.Item name="fs_secret" label="签名校验密钥" extra="安全设置为签名校验时填写">
                <Input.Password placeholder="可选" />
              </Form.Item>
            </>
          )}
        </Form>
      </Modal>
    </div>
  )
}
