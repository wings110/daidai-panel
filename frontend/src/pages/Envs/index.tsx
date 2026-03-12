import { useEffect, useState, useMemo } from 'react'
import {
  Card, Table, Button, Space, Input, Modal, Form,
  Switch, Typography, message, Popconfirm, Tag, Tooltip, Select, Radio, Upload, Segmented, Badge,
} from 'antd'
import {
  PlusOutlined, SearchOutlined, ReloadOutlined,
  EditOutlined, DeleteOutlined, ImportOutlined, ExportOutlined,
  MenuOutlined, DownloadOutlined, UploadOutlined,
  UnorderedListOutlined, AppstoreOutlined,
} from '@ant-design/icons'
import { envApi } from '../../services/api'

const { Title, Text } = Typography

interface EnvRecord {
  id: number
  name: string
  value: string
  remarks: string
  enabled: boolean
  group: string
  created_at: string
  updated_at: string
}

export default function Envs() {
  const [envs, setEnvs] = useState<EnvRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [keyword, setKeyword] = useState('')
  const [selectedGroup, setSelectedGroup] = useState<string>('')
  const [groups, setGroups] = useState<string[]>([])
  const [modalOpen, setModalOpen] = useState(false)
  const [editingEnv, setEditingEnv] = useState<EnvRecord | null>(null)
  const [selectedKeys, setSelectedKeys] = useState<number[]>([])
  const [importOpen, setImportOpen] = useState(false)
  const [importText, setImportText] = useState('')
  const [importMode, setImportMode] = useState<'merge' | 'replace'>('merge')
  const [importLoading, setImportLoading] = useState(false)
  const [exportOpen, setExportOpen] = useState(false)
  const [dragIndex, setDragIndex] = useState<number | null>(null)
  const [viewMode, setViewMode] = useState<'list' | 'group'>('list')
  const [expandedGroupKeys, setExpandedGroupKeys] = useState<string[]>([])
  const [form] = Form.useForm()

  useEffect(() => {
    fetchEnvs()
    fetchGroups()
  }, [page, selectedGroup])

  const fetchGroups = async () => {
    try {
      const res = await envApi.listGroups()
      setGroups(res.data.data || [])
    } catch {
      // 忽略错误
    }
  }

  const fetchEnvs = async () => {
    setLoading(true)
    try {
      const res = await envApi.list({ keyword, group: selectedGroup, page, page_size: 20 })
      setEnvs(res.data.data || [])
      setTotal(res.data.total || 0)
    } catch {
      message.error('获取环境变量失败')
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = () => {
    setEditingEnv(null)
    form.resetFields()
    setModalOpen(true)
  }

  const handleEdit = (record: EnvRecord) => {
    setEditingEnv(record)
    form.setFieldsValue(record)
    setModalOpen(true)
  }

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      if (editingEnv) {
        await envApi.update(editingEnv.id, values)
        message.success('更新成功')
      } else {
        await envApi.create(values)
        message.success('创建成功')
      }
      setModalOpen(false)
      fetchEnvs()
    } catch (err: any) {
      if (err?.response?.data?.error) {
        message.error(err.response.data.error)
      }
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await envApi.delete(id)
      message.success('删除成功')
      fetchEnvs()
    } catch {
      message.error('删除失败')
    }
  }

  const handleToggle = async (record: EnvRecord) => {
    try {
      if (record.enabled) {
        await envApi.disable(record.id)
        message.success('已禁用')
      } else {
        await envApi.enable(record.id)
        message.success('已启用')
      }
      fetchEnvs()
    } catch {
      message.error('操作失败')
    }
  }

  const handleBatchImport = async () => {
    if (!importText.trim()) {
      message.warning('请输入要导入的环境变量')
      return
    }

    try {
      const envs = JSON.parse(importText)
      if (!Array.isArray(envs)) {
        message.error('JSON 格式错误，应为数组')
        return
      }

      setImportLoading(true)
      const res = await envApi.import(envs, importMode)
      setImportLoading(false)
      setImportOpen(false)
      setImportText('')

      if (res.data.errors && res.data.errors.length > 0) {
        Modal.warning({
          title: '导入完成（部分失败）',
          content: (
            <div>
              <p>{res.data.message}</p>
              <div style={{ maxHeight: 200, overflow: 'auto', marginTop: 8 }}>
                {res.data.errors.map((err: string, i: number) => (
                  <div key={i} style={{ fontSize: 12, color: '#ff4d4f' }}>{err}</div>
                ))}
              </div>
            </div>
          ),
        })
      } else {
        message.success(res.data.message)
      }

      fetchEnvs()
      fetchGroups()
    } catch (err: any) {
      setImportLoading(false)
      if (err?.response?.data?.error) {
        message.error(err.response.data.error)
      } else {
        message.error('JSON 解析失败，请检查格式')
      }
    }
  }

  const handleExport = async () => {
    try {
      const res = await envApi.exportAll()
      const data = res.data.data || []
      const json = JSON.stringify(data, null, 2)
      const blob = new Blob([json], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `envs_${new Date().toISOString().slice(0, 10)}.json`
      a.click()
      URL.revokeObjectURL(url)
      message.success('导出成功')
      setExportOpen(false)
    } catch {
      message.error('导出失败')
    }
  }

  const handleBatchDelete = async () => {
    if (selectedKeys.length === 0) return
    try {
      await envApi.batchDelete(selectedKeys)
      message.success('批量删除成功')
      setSelectedKeys([])
      fetchEnvs()
    } catch {
      message.error('批量删除失败')
    }
  }

  const handleDragStart = (index: number) => {
    setDragIndex(index)
  }

  const handleDrop = async (targetIndex: number) => {
    if (dragIndex === null || dragIndex === targetIndex) return
    const newList = [...envs]
    const [moved] = newList.splice(dragIndex, 1)
    newList.splice(targetIndex, 0, moved)
    setEnvs(newList)
    setDragIndex(null)
    try {
      await envApi.updateSort(newList.map(e => e.id))
    } catch {
      message.error('排序保存失败')
      fetchEnvs()
    }
  }

  const columns = [
    {
      title: '',
      key: 'drag',
      width: 28,
      className: 'drag-column',
      render: (_: any, __: any, index: number) => (
        <MenuOutlined
          style={{ cursor: 'grab', color: '#999', fontSize: 12 }}
          draggable
          onDragStart={() => handleDragStart(index)}
        />
      ),
    },
    {
      title: '变量名',
      dataIndex: 'name',
      key: 'name',
      width: 200,
      render: (v: string) => <code style={{ fontSize: 13, color: '#1677FF' }}>{v}</code>,
    },
    {
      title: '值',
      dataIndex: 'value',
      key: 'value',
      ellipsis: true,
      render: (v: string) => (
        <Text copyable={{ text: v }} style={{ fontSize: 13 }}>
          {v.length > 50 ? v.slice(0, 50) + '...' : v}
        </Text>
      ),
    },
    {
      title: '分组',
      dataIndex: 'group',
      key: 'group',
      width: 120,
      render: (g: string) => g ? <Tag color="blue">{g}</Tag> : <Text type="secondary">-</Text>,
    },
    {
      title: '备注',
      dataIndex: 'remarks',
      key: 'remarks',
      width: 160,
      ellipsis: true,
    },
    {
      title: '状态',
      dataIndex: 'enabled',
      key: 'enabled',
      width: 80,
      render: (enabled: boolean, record: EnvRecord) => (
        <Switch
          size="small"
          checked={enabled}
          onChange={() => handleToggle(record)}
        />
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 120,
      render: (_: any, record: EnvRecord) => (
        <Space size={4}>
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

  // 按变量名分组数据（用于分组视图）
  interface GroupedEnv {
    key: string
    name: string
    count: number
    enabledCount: number
    items: EnvRecord[]
  }

  const groupedEnvs = useMemo<GroupedEnv[]>(() => {
    if (viewMode !== 'group') return []
    const map = new Map<string, EnvRecord[]>()
    for (const env of envs) {
      const list = map.get(env.name) || []
      list.push(env)
      map.set(env.name, list)
    }
    return Array.from(map.entries()).map(([name, items]) => ({
      key: name,
      name,
      count: items.length,
      enabledCount: items.filter(i => i.enabled).length,
      items,
    }))
  }, [envs, viewMode])

  const groupColumns = [
    {
      title: '变量名',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record: GroupedEnv) => (
        <Space>
          <code style={{ fontSize: 13, color: '#1677FF', fontWeight: 500 }}>{name}</code>
          {record.count > 1 && (
            <Badge count={record.count} style={{ backgroundColor: '#1677FF' }} />
          )}
        </Space>
      ),
    },
    {
      title: '数量',
      key: 'count',
      width: 120,
      render: (_: any, record: GroupedEnv) => (
        <Text type="secondary">
          {record.enabledCount}/{record.count} 已启用
        </Text>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 160,
      render: (_: any, record: GroupedEnv) => (
        <Space size={4}>
          <Tooltip title="全部启用">
            <Button
              type="text"
              size="small"
              onClick={async () => {
                try {
                  for (const item of record.items.filter(i => !i.enabled)) {
                    await envApi.enable(item.id)
                  }
                  message.success(`已启用 ${record.name} 全部变量`)
                  fetchEnvs()
                } catch { message.error('操作失败') }
              }}
            >
              全部启用
            </Button>
          </Tooltip>
          <Tooltip title="全部禁用">
            <Button
              type="text"
              size="small"
              onClick={async () => {
                try {
                  for (const item of record.items.filter(i => i.enabled)) {
                    await envApi.disable(item.id)
                  }
                  message.success(`已禁用 ${record.name} 全部变量`)
                  fetchEnvs()
                } catch { message.error('操作失败') }
              }}
            >
              全部禁用
            </Button>
          </Tooltip>
          <Popconfirm
            title={`确定删除 ${record.name} 的全部 ${record.count} 个变量？`}
            onConfirm={async () => {
              try {
                await envApi.batchDelete(record.items.map(i => i.id))
                message.success('批量删除成功')
                fetchEnvs()
              } catch { message.error('删除失败') }
            }}
          >
            <Button type="text" size="small" danger>全部删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div className="animate-fade-in">
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <Title level={4} style={{ margin: 0, fontWeight: 600 }}>环境变量</Title>
        <Space>
          <Segmented
            value={viewMode}
            onChange={(v) => setViewMode(v as 'list' | 'group')}
            options={[
              { label: '列表', value: 'list', icon: <UnorderedListOutlined /> },
              { label: '分组', value: 'group', icon: <AppstoreOutlined /> },
            ]}
            size="small"
          />
          <Select
            placeholder="选择分组"
            value={selectedGroup || undefined}
            onChange={(v) => { setSelectedGroup(v || ''); setPage(1) }}
            style={{ width: 150 }}
            allowClear
            options={[
              { label: '全部分组', value: '' },
              ...groups.map(g => ({ label: g, value: g })),
            ]}
          />
          <Input
            placeholder="搜索变量名"
            prefix={<SearchOutlined />}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onPressEnter={() => { setPage(1); fetchEnvs() }}
            style={{ width: 200, borderRadius: 6 }}
            allowClear
          />
          <Button icon={<ReloadOutlined />} onClick={fetchEnvs}>刷新</Button>
          <Button icon={<ExportOutlined />} onClick={() => setExportOpen(true)}>导出</Button>
          <Button icon={<ImportOutlined />} onClick={() => setImportOpen(true)}>导入</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>新建变量</Button>
        </Space>
      </div>

      {selectedKeys.length > 0 && (
        <Card size="small" style={{ marginBottom: 16, borderRadius: 8, background: '#f0f5ff' }}>
          <Space>
            <span>已选择 <strong>{selectedKeys.length}</strong> 项</span>
            <Popconfirm title="确定批量删除？" onConfirm={handleBatchDelete}>
              <Button size="small" danger>批量删除</Button>
            </Popconfirm>
            <Button size="small" type="link" onClick={() => setSelectedKeys([])}>取消选择</Button>
          </Space>
        </Card>
      )}

      <Card style={{ borderRadius: 10 }} styles={{ body: { padding: 0 } }}>
        {viewMode === 'list' ? (
        <Table
          dataSource={envs}
          columns={columns}
          rowKey="id"
          loading={loading}
          size="middle"
          scroll={{ x: 850, y: 600 }}
          virtual
          rowSelection={{
            selectedRowKeys: selectedKeys,
            onChange: (keys) => setSelectedKeys(keys as number[]),
            columnWidth: 36,
          }}
          onRow={(_, index) => ({
            draggable: true,
            onDragOver: (e: React.DragEvent) => e.preventDefault(),
            onDrop: () => handleDrop(index!),
          })}
          pagination={{
            current: page,
            total,
            pageSize: 20,
            showTotal: (t) => `共 ${t} 条`,
            onChange: setPage,
          }}
          locale={{ emptyText: '暂无环境变量' }}
        />
        ) : (
        <Table
          dataSource={groupedEnvs}
          columns={groupColumns as any}
          rowKey="key"
          loading={loading}
          size="middle"
          expandable={{
            expandedRowKeys: expandedGroupKeys,
            onExpandedRowsChange: (keys) => setExpandedGroupKeys(keys as string[]),
            expandedRowRender: (record: GroupedEnv) => (
              <Table
                dataSource={record.items}
                rowKey="id"
                size="small"
                pagination={false}
                columns={[
                  {
                    title: '值',
                    dataIndex: 'value',
                    key: 'value',
                    ellipsis: true,
                    render: (v: string) => (
                      <Text copyable={{ text: v }} style={{ fontSize: 13 }}>
                        {v.length > 60 ? v.slice(0, 60) + '...' : v}
                      </Text>
                    ),
                  },
                  {
                    title: '分组',
                    dataIndex: 'group',
                    key: 'group',
                    width: 120,
                    render: (g: string) => g ? <Tag color="blue">{g}</Tag> : <Text type="secondary">-</Text>,
                  },
                  {
                    title: '备注',
                    dataIndex: 'remarks',
                    key: 'remarks',
                    width: 200,
                    ellipsis: true,
                  },
                  {
                    title: '状态',
                    dataIndex: 'enabled',
                    key: 'enabled',
                    width: 80,
                    render: (enabled: boolean, item: EnvRecord) => (
                      <Switch size="small" checked={enabled} onChange={() => handleToggle(item)} />
                    ),
                  },
                  {
                    title: '操作',
                    key: 'actions',
                    width: 100,
                    render: (_: any, item: EnvRecord) => (
                      <Space size={4}>
                        <Tooltip title="编辑">
                          <Button type="text" size="small" icon={<EditOutlined />} onClick={() => handleEdit(item)} />
                        </Tooltip>
                        <Popconfirm title="确定删除？" onConfirm={() => handleDelete(item.id)}>
                          <Tooltip title="删除">
                            <Button type="text" size="small" icon={<DeleteOutlined />} danger />
                          </Tooltip>
                        </Popconfirm>
                      </Space>
                    ),
                  },
                ]}
              />
            ),
          }}
          pagination={{
            current: page,
            total: groupedEnvs.length,
            pageSize: 50,
            showTotal: (t) => `共 ${t} 组`,
          }}
          locale={{ emptyText: '暂无环境变量' }}
        />
        )}
      </Card>

      <Modal
        title={editingEnv ? '编辑变量' : '新建变量'}
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
            label="变量名"
            rules={[
              { required: true, message: '请输入变量名' },
              { pattern: /^[A-Za-z_][A-Za-z0-9_]*$/, message: '只允许字母、数字和下划线' },
            ]}
          >
            <Input placeholder="例如：MY_API_KEY" />
          </Form.Item>
          <Form.Item
            name="value"
            label="变量值"
            rules={[{ required: true, message: '请输入变量值' }]}
          >
            <Input.TextArea rows={3} placeholder="变量值" />
          </Form.Item>
          <Form.Item name="group" label="分组">
            <Select
              placeholder="选择或输入分组"
              allowClear
              showSearch
              mode="tags"
              maxCount={1}
              options={groups.map(g => ({ label: g, value: g }))}
            />
          </Form.Item>
          <Form.Item name="remarks" label="备注">
            <Input placeholder="可选备注" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="导入环境变量"
        open={importOpen}
        onOk={handleBatchImport}
        onCancel={() => { setImportOpen(false); setImportText(''); setImportMode('merge') }}
        okText="导入"
        cancelText="取消"
        confirmLoading={importLoading}
        width={640}
      >
        <div style={{ marginBottom: 16 }}>
          <Radio.Group value={importMode} onChange={e => setImportMode(e.target.value)}>
            <Radio value="merge">合并模式（保留现有变量，更新重复项）</Radio>
            <Radio value="replace">替换模式（删除所有现有变量）</Radio>
          </Radio.Group>
        </div>
        <div style={{ marginBottom: 12 }}>
          <Upload
            accept=".json"
            showUploadList={false}
            beforeUpload={(file) => {
              const reader = new FileReader()
              reader.onload = (e) => {
                const content = e.target?.result as string
                if (content) {
                  setImportText(content)
                  message.success(`已加载文件: ${file.name}`)
                }
              }
              reader.readAsText(file)
              return false
            }}
          >
            <Button icon={<UploadOutlined />}>选择 JSON 文件</Button>
          </Upload>
          <Text type="secondary" style={{ fontSize: 13, marginLeft: 12 }}>
            支持呆呆面板和青龙面板导出格式
          </Text>
        </div>
        <div style={{ marginBottom: 12 }}>
          <Text type="secondary" style={{ fontSize: 13 }}>
            也可以直接粘贴 JSON 格式的环境变量数组：
          </Text>
          <pre style={{
            background: '#f5f5f5', padding: 12, borderRadius: 6, fontSize: 12,
            marginTop: 8, color: '#595959', lineHeight: 1.8,
          }}>
{`[
  { "name": "MY_KEY", "value": "xxx", "remarks": "备注" },
  { "name": "MY_KEY", "value": "yyy", "status": 0 }
]
// status: 0=启用, 1=禁用 (青龙格式)`}
          </pre>
        </div>
        <Input.TextArea
          rows={10}
          value={importText}
          onChange={e => setImportText(e.target.value)}
          placeholder="粘贴 JSON 格式的环境变量数组，或通过上方按钮选择文件"
          style={{ fontFamily: 'monospace', fontSize: 13 }}
        />
      </Modal>

      <Modal
        title="导出环境变量"
        open={exportOpen}
        onOk={handleExport}
        onCancel={() => setExportOpen(false)}
        okText="导出为 JSON"
        cancelText="取消"
        width={500}
      >
        <div style={{ padding: '16px 0' }}>
          <Text>
            将导出所有环境变量为 JSON 格式文件，包含变量名、值、分组、备注和启用状态。
          </Text>
          <div style={{ marginTop: 16, padding: 12, background: '#f0f5ff', borderRadius: 6 }}>
            <Text type="secondary" style={{ fontSize: 13 }}>
              <DownloadOutlined /> 文件名格式：envs_YYYY-MM-DD.json
            </Text>
          </div>
        </div>
      </Modal>
    </div>
  )
}
