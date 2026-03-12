import { useEffect, useState, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  Card, Table, Button, Space, Tag, Input, Modal, Form,
  Select, message, Popconfirm, Tooltip, Typography, Switch,
  InputNumber, Row, Col, Descriptions, List, Dropdown, Upload,
} from 'antd'
import {
  PlusOutlined, SearchOutlined, PlayCircleOutlined,
  PauseCircleOutlined, DeleteOutlined, EditOutlined,
  ReloadOutlined, CaretRightOutlined, StopOutlined,
  EyeOutlined, FileTextOutlined, PushpinOutlined, PushpinFilled,
  DownloadOutlined, FolderOpenOutlined, CopyOutlined, MoreOutlined,
  ClearOutlined, ExportOutlined, ImportOutlined,
} from '@ant-design/icons'
import { taskApi } from '../../services/api'
import type { TaskData } from '../../services/api'
import dayjs from 'dayjs'
import CronInput, { describeCron } from '../../components/CronInput'
import { useTaskLiveLogs } from '../../hooks/useTaskLiveLogs'
import { handleApiError, handleApiSuccess } from '../../utils/apiHelper'
import { formatUTCTime } from '../../utils/timeHelper'
import Ansi from 'ansi-to-react'

const { Title } = Typography

interface TaskRecord {
  id: number
  name: string
  command: string
  cron_expression: string
  status: number
  labels: string[]
  last_run_at: string | null
  last_run_status: number | null
  timeout: number
  max_retries: number
  retry_interval: number
  notify_on_failure: boolean
  depends_on: number | null
  is_pinned: boolean
  created_at: string
}

interface LogFile {
  filename: string
  size: number
  modified_at: string
  path: string
}

export default function Tasks() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [tasks, setTasks] = useState<TaskRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [keyword, setKeyword] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editingTask, setEditingTask] = useState<TaskRecord | null>(null)
  const [selectedKeys, setSelectedKeys] = useState<number[]>([])
  const [detailOpen, setDetailOpen] = useState(false)
  const [detailTask, setDetailTask] = useState<TaskRecord | null>(null)

  // 实时日志相关状态
  const [logOpen, setLogOpen] = useState(false)
  const [logTaskId, setLogTaskId] = useState<number | null>(null)
  const [logTaskName, setLogTaskName] = useState('')
  const [autoScroll, setAutoScroll] = useState(true)

  // 日志容器引用
  const logContainerRef = useRef<HTMLDivElement>(null)

  // 日志文件列表相关状态
  const [logFilesOpen, setLogFilesOpen] = useState(false)
  const [logFiles, setLogFiles] = useState<LogFile[]>([])
  const [loadingLogFiles, setLoadingLogFiles] = useState(false)
  const [selectedLogFile, setSelectedLogFile] = useState<string | null>(null)
  const [logFileContent, setLogFileContent] = useState('')
  const [loadingLogContent, setLoadingLogContent] = useState(false)

  // 使用SSE Hook获取实时日志
  const { logs, done: logDone, error: logError, isHistorical } = useTaskLiveLogs(logTaskId, logOpen)

  const [form] = Form.useForm()

  useEffect(() => {
    fetchTasks()
  }, [page])

  // 处理从脚本页上传后跳转过来的自动创建
  useEffect(() => {
    if (searchParams.get('autoCreate') === '1') {
      const name = searchParams.get('name') || ''
      const command = searchParams.get('command') || ''
      setEditingTask(null)
      form.resetFields()
      form.setFieldsValue({
        name,
        command,
        timeout: 300,
        max_retries: 0,
        retry_interval: 60,
        notify_on_failure: true,
      })
      setModalOpen(true)
      // 清除 URL 参数，避免刷新时重复弹出
      setSearchParams({}, { replace: true })
    }
  }, [searchParams])

  const fetchTasks = async () => {
    setLoading(true)
    try {
      const res = await taskApi.list({ keyword, page, page_size: 20 })
      setTasks(res.data.data || [])
      setTotal(res.data.total || 0)
    } catch (error) {
      handleApiError(error, '获取任务列表失败')
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = () => {
    setEditingTask(null)
    form.resetFields()
    form.setFieldsValue({
      timeout: 300,
      max_retries: 0,
      retry_interval: 60,
      notify_on_failure: true,
    })
    setModalOpen(true)
  }

  const handleEdit = (record: TaskRecord) => {
    setEditingTask(record)
    form.setFieldsValue({
      ...record,
      labels: record.labels?.join(',') || '',
    })
    setModalOpen(true)
  }

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      const data: TaskData = {
        ...values,
        labels: values.labels ? values.labels.split(',').map((s: string) => s.trim()).filter(Boolean) : [],
      }

      if (editingTask) {
        await taskApi.update(editingTask.id, data)
        handleApiSuccess('任务更新成功')
      } else {
        await taskApi.create(data)
        handleApiSuccess('任务创建成功')
      }

      setModalOpen(false)
      fetchTasks()
    } catch (err: any) {
      // 表单验证错误不需要显示，Ant Design会自动处理
      if (err?.errorFields) {
        return
      }
      handleApiError(err, '保存任务失败')
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await taskApi.delete(id)
      handleApiSuccess('任务删除成功')
      fetchTasks()
    } catch (error) {
      handleApiError(error, '删除任务失败')
    }
  }

  const handleRun = async (id: number) => {
    try {
      await taskApi.run(id)
      message.success('任务已触发执行，正在获取日志...')

      // 等待一小段时间让任务开始执行
      await new Promise(resolve => setTimeout(resolve, 500))

      // 获取任务信息并打开日志查看
      const task = tasks.find(t => t.id === id)
      if (task) {
        setLogTaskId(id)
        setLogTaskName(task.name)
        setLogOpen(true)
      }

      setTimeout(fetchTasks, 1000)
    } catch (error) {
      handleApiError(error, '执行任务失败')
    }
  }

  const handleToggleStatus = async (record: TaskRecord) => {
    try {
      if (record.status === 0) {
        await taskApi.enable(record.id)
        handleApiSuccess('任务已启用')
      } else {
        await taskApi.disable(record.id)
        handleApiSuccess('任务已禁用')
      }
      fetchTasks()
    } catch (error) {
      handleApiError(error, '操作失败')
    }
  }

  const handleBatch = async (action: string) => {
    if (selectedKeys.length === 0) {
      message.warning('请先选择任务')
      return
    }
    try {
      await taskApi.batch(selectedKeys, action)
      handleApiSuccess('批量操作成功')
      setSelectedKeys([])
      fetchTasks()
    } catch (error) {
      handleApiError(error, '批量操作失败')
    }
  }

  const handleTogglePin = async (record: TaskRecord) => {
    try {
      if (record.is_pinned) {
        await taskApi.unpin(record.id)
        handleApiSuccess('已取消置顶')
      } else {
        await taskApi.pin(record.id)
        handleApiSuccess('已置顶')
      }
      fetchTasks()
    } catch (error) {
      handleApiError(error, '操作失败')
    }
  }

  const handleCopy = async (record: TaskRecord) => {
    try {
      await taskApi.copy(record.id)
      handleApiSuccess('任务复制成功')
      fetchTasks()
    } catch (error) {
      handleApiError(error, '复制任务失败')
    }
  }

  const handleViewLogs = async (record: TaskRecord) => {
    setLogTaskId(record.id)
    setLogTaskName(record.name)
    setLogOpen(true)
  }

  const handleViewLogFiles = async (record: TaskRecord) => {
    setLogTaskId(record.id)
    setLogTaskName(record.name)
    setLogFilesOpen(true)
    setSelectedLogFile(null)
    setLogFileContent('')
    await fetchLogFiles(record.id)
  }

  const fetchLogFiles = async (taskId: number) => {
    setLoadingLogFiles(true)
    try {
      const res = await taskApi.listLogFiles(taskId)
      setLogFiles(res.data.data || [])
    } catch (error) {
      handleApiError(error, '获取日志文件列表失败')
    } finally {
      setLoadingLogFiles(false)
    }
  }

  const handleSelectLogFile = async (filename: string) => {
    if (!logTaskId) return
    setSelectedLogFile(filename)
    setLoadingLogContent(true)
    try {
      const res = await taskApi.getLogFileContent(logTaskId, filename)
      setLogFileContent(res.data.content || '')
    } catch (error) {
      handleApiError(error, '获取日志内容失败')
    } finally {
      setLoadingLogContent(false)
    }
  }

  const handleDeleteLogFile = async (filename: string) => {
    if (!logTaskId) return
    try {
      await taskApi.deleteLogFile(logTaskId, filename)
      handleApiSuccess('日志文件删除成功')
      await fetchLogFiles(logTaskId)
      if (selectedLogFile === filename) {
        setSelectedLogFile(null)
        setLogFileContent('')
      }
    } catch (error) {
      handleApiError(error, '删除日志文件失败')
    }
  }

  const handleDownloadLogFile = (filename: string) => {
    if (!logTaskId) return
    const url = taskApi.downloadLogFile(logTaskId, filename)
    const token = localStorage.getItem('access_token')
    const link = document.createElement('a')
    link.href = `${url}?token=${token}`
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  const handleCleanLogs = async (days: number) => {
    try {
      const res = await taskApi.cleanOldLogs(days)
      handleApiSuccess(res.data.message)
    } catch (error) {
      handleApiError(error, '清理日志失败')
    }
  }

  const handleExportTasks = async () => {
    try {
      const res = await taskApi.exportTasks()
      const data = JSON.stringify(res.data.data, null, 2)
      const blob = new Blob([data], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `tasks_${dayjs().format('YYYY-MM-DD_HH-mm-ss')}.json`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
      handleApiSuccess('任务导出成功')
    } catch (error) {
      handleApiError(error, '导出任务失败')
    }
  }

  const handleImportTasks = async (file: File) => {
    try {
      const text = await file.text()
      const tasks = JSON.parse(text)
      const res = await taskApi.importTasks(tasks)
      handleApiSuccess(res.data.message)
      if (res.data.errors && res.data.errors.length > 0) {
        Modal.warning({
          title: '部分任务导入失败',
          content: (
            <div>
              {res.data.errors.map((err: string, idx: number) => (
                <div key={idx} style={{ marginBottom: 4 }}>{err}</div>
              ))}
            </div>
          ),
        })
      }
      fetchTasks()
    } catch (error: any) {
      if (error.message?.includes('JSON')) {
        handleApiError(error, '文件格式错误，请上传有效的 JSON 文件')
      } else {
        handleApiError(error, '导入任务失败')
      }
    }
    return false
  }

  const handleCloseLog = () => {
    setLogOpen(false)
    setLogTaskId(null)
  }

  // 显示日志错误
  useEffect(() => {
    if (logError) {
      message.error(logError)
    }
  }, [logError])

  // 自动滚动到底部
  useEffect(() => {
    if (autoScroll && logContainerRef.current && logs.length > 0) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight
    }
  }, [logs, autoScroll])

  const statusTag = (status: number) => {
    const map: Record<number, { color: string; text: string }> = {
      0: { color: 'default', text: '已禁用' },
      1: { color: 'processing', text: '已启用' },
      2: { color: 'warning', text: '运行中' },
    }
    const s = map[status] || { color: 'default', text: '未知' }
    return <Tag color={s.color}>{s.text}</Tag>
  }

  const runStatusTag = (status: number | null) => {
    if (status === null || status === undefined) return <Tag>未执行</Tag>
    return status === 0
      ? <Tag color="success">成功</Tag>
      : <Tag color="error">失败</Tag>
  }

  const columns = [
    {
      title: '任务名称',
      dataIndex: 'name',
      key: 'name',
      ellipsis: true,
      width: 200,
      sorter: (a: TaskRecord, b: TaskRecord) => a.name.localeCompare(b.name),
      render: (v: string, record: TaskRecord) => (
        <Space size={4}>
          {record.is_pinned && (
            <PushpinFilled style={{ color: '#faad14', fontSize: 14 }} />
          )}
          <a onClick={() => { setDetailTask(record); setDetailOpen(true) }} style={{ fontWeight: 500 }}>{v}</a>
        </Space>
      ),
    },
    {
      title: '执行脚本',
      dataIndex: 'command',
      key: 'command',
      ellipsis: true,
      width: 180,
      render: (v: string) => <code style={{ fontSize: 12 }}>{v}</code>,
    },
    {
      title: 'Cron 表达式',
      dataIndex: 'cron_expression',
      key: 'cron_expression',
      width: 180,
      render: (v: string) => (
        <Tooltip title={describeCron(v)}>
          <code style={{ fontSize: 12 }}>{v}</code>
        </Tooltip>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      sorter: (a: TaskRecord, b: TaskRecord) => a.status - b.status,
      render: statusTag,
    },
    {
      title: '上次结果',
      dataIndex: 'last_run_status',
      key: 'last_run_status',
      width: 90,
      sorter: (a: TaskRecord, b: TaskRecord) => (a.last_run_status ?? -1) - (b.last_run_status ?? -1),
      render: runStatusTag,
    },
    {
      title: '上次执行',
      dataIndex: 'last_run_at',
      key: 'last_run_at',
      width: 170,
      sorter: (a: TaskRecord, b: TaskRecord) => {
        if (!a.last_run_at && !b.last_run_at) return 0
        if (!a.last_run_at) return -1
        if (!b.last_run_at) return 1
        return new Date(a.last_run_at).getTime() - new Date(b.last_run_at).getTime()
      },
      render: (v: string) => formatUTCTime(v),
    },
    {
      title: '依赖',
      dataIndex: 'depends_on',
      key: 'depends_on',
      width: 120,
      render: (v: number | null) => {
        if (!v) return <span style={{ color: '#8c8c8c' }}>-</span>
        const dependTask = tasks.find(t => t.id === v)
        return (
          <Tooltip title={dependTask?.name || `任务 #${v}`}>
            <Tag color="blue" style={{ cursor: 'pointer' }}>
              {dependTask?.name || `#${v}`}
            </Tag>
          </Tooltip>
        )
      },
    },
    {
      title: '操作',
      key: 'actions',
      width: 240,
      fixed: 'right' as const,
      render: (_: any, record: TaskRecord) => (
        <Space size={4}>
          <Tooltip title="详情">
            <Button
              type="text"
              size="small"
              icon={<EyeOutlined />}
              onClick={() => { setDetailTask(record); setDetailOpen(true) }}
            />
          </Tooltip>
          <Tooltip title="日志">
            <Button
              type="text"
              size="small"
              icon={<FileTextOutlined />}
              style={{ color: '#1677FF' }}
              onClick={() => handleViewLogs(record)}
            />
          </Tooltip>
          <Tooltip title="日志文件">
            <Button
              type="text"
              size="small"
              icon={<FolderOpenOutlined />}
              style={{ color: '#52c41a' }}
              onClick={() => handleViewLogFiles(record)}
            />
          </Tooltip>
          <Tooltip title="执行">
            <Button
              type="text"
              size="small"
              icon={<CaretRightOutlined />}
              style={{ color: '#52c41a' }}
              onClick={() => handleRun(record.id)}
              disabled={record.status === 2}
            />
          </Tooltip>
          <Tooltip title={record.is_pinned ? '取消置顶' : '置顶'}>
            <Button
              type="text"
              size="small"
              icon={record.is_pinned ? <PushpinFilled /> : <PushpinOutlined />}
              style={{ color: record.is_pinned ? '#faad14' : undefined }}
              onClick={() => handleTogglePin(record)}
            />
          </Tooltip>
          <Tooltip title={record.status === 0 ? '启用' : '禁用'}>
            <Button
              type="text"
              size="small"
              icon={record.status === 0 ? <PlayCircleOutlined /> : <PauseCircleOutlined />}
              onClick={() => handleToggleStatus(record)}
            />
          </Tooltip>
          <Tooltip title="编辑">
            <Button
              type="text"
              size="small"
              icon={<EditOutlined />}
              onClick={() => handleEdit(record)}
            />
          </Tooltip>
          <Tooltip title="复制">
            <Button
              type="text"
              size="small"
              icon={<CopyOutlined />}
              onClick={() => handleCopy(record)}
            />
          </Tooltip>
          <Popconfirm title="确定删除该任务？" onConfirm={() => handleDelete(record.id)}>
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
        <Title level={4} style={{ margin: 0, fontWeight: 600 }}>定时任务</Title>
        <Space>
          <Input
            placeholder="搜索任务名称"
            prefix={<SearchOutlined />}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onPressEnter={() => { setPage(1); fetchTasks() }}
            style={{ width: 220, borderRadius: 6 }}
            allowClear
          />
          <Button icon={<ReloadOutlined />} onClick={fetchTasks}>刷新</Button>
          <Dropdown
            menu={{
              items: [
                {
                  key: 'export',
                  label: '导出任务',
                  icon: <ExportOutlined />,
                  onClick: handleExportTasks,
                },
                {
                  key: 'import',
                  label: (
                    <Upload
                      accept=".json"
                      showUploadList={false}
                      beforeUpload={handleImportTasks}
                    >
                      <span>导入任务</span>
                    </Upload>
                  ),
                  icon: <ImportOutlined />,
                },
                { type: 'divider' },
                {
                  key: 'clean-7',
                  label: '清理 7 天前的日志',
                  icon: <ClearOutlined />,
                  onClick: () => {
                    Modal.confirm({
                      title: '确认清理日志',
                      content: '确定要清理 7 天前的所有任务日志吗？',
                      onOk: () => handleCleanLogs(7),
                    })
                  },
                },
                {
                  key: 'clean-30',
                  label: '清理 30 天前的日志',
                  icon: <ClearOutlined />,
                  onClick: () => {
                    Modal.confirm({
                      title: '确认清理日志',
                      content: '确定要清理 30 天前的所有任务日志吗？',
                      onOk: () => handleCleanLogs(30),
                    })
                  },
                },
              ],
            }}
          >
            <Button icon={<MoreOutlined />}>更多</Button>
          </Dropdown>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
            新建任务
          </Button>
        </Space>
      </div>

      {/* 批量操作栏 */}
      {selectedKeys.length > 0 && (
        <Card size="small" style={{ marginBottom: 16, borderRadius: 8, background: '#f0f5ff' }}>
          <Space>
            <span>已选择 <strong>{selectedKeys.length}</strong> 项</span>
            <Button size="small" onClick={() => handleBatch('enable')}>批量启用</Button>
            <Button size="small" onClick={() => handleBatch('disable')}>批量禁用</Button>
            <Button size="small" onClick={() => handleBatch('run')}>批量执行</Button>
            <Button size="small" icon={<PushpinFilled />} onClick={() => handleBatch('pin')}>批量置顶</Button>
            <Button size="small" icon={<PushpinOutlined />} onClick={() => handleBatch('unpin')}>取消置顶</Button>
            <Popconfirm title="确定批量删除？" onConfirm={() => handleBatch('delete')}>
              <Button size="small" danger>批量删除</Button>
            </Popconfirm>
            <Button size="small" type="link" onClick={() => setSelectedKeys([])}>取消选择</Button>
          </Space>
        </Card>
      )}

      {/* 任务列表 */}
      <Card style={{ borderRadius: 10 }} styles={{ body: { padding: 0 } }}>
        <Table
          dataSource={tasks}
          columns={columns}
          rowKey="id"
          loading={loading}
          size="middle"
          scroll={{ x: 1000 }}
          rowSelection={{
            selectedRowKeys: selectedKeys,
            onChange: (keys) => setSelectedKeys(keys as number[]),
          }}
          pagination={{
            current: page,
            total,
            pageSize: 20,
            showTotal: (t) => `共 ${t} 条`,
            showSizeChanger: false,
            onChange: setPage,
          }}
          locale={{ emptyText: '暂无任务' }}
        />
      </Card>

      {/* 新建/编辑弹窗 */}
      <Modal
        title={editingTask ? '编辑任务' : '新建任务'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        width={580}
        okText="保存"
        cancelText="取消"
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="name"
            label="任务名称"
            rules={[{ required: true, message: '请输入任务名称' }]}
          >
            <Input placeholder="例如：签到任务" />
          </Form.Item>

          <Form.Item
            name="command"
            label="命令/脚本"
            rules={[
              { required: true, message: '请输入执行命令' },
              {
                pattern: /^(python|node|bash|ts-node|npx\s+ts-node)\s+[\w\u4e00-\u9fff\-./]+\.(py|js|sh|ts)$/u,
                message: '命令格式错误，示例：python script.py 或 node app.js'
              },
            ]}
          >
            <Input placeholder="例如：python checkin.py 或 node app.js" />
          </Form.Item>

          <Form.Item
            name="cron_expression"
            label="Cron 表达式"
            rules={[{ required: true, message: '请输入 Cron 表达式' }]}
          >
            <CronInput />
          </Form.Item>

          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="timeout" label="超时(秒)">
                <InputNumber min={10} max={86400} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="max_retries" label="重试次数">
                <InputNumber min={0} max={10} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="retry_interval" label="重试间隔(秒)">
                <InputNumber min={5} max={3600} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item name="notify_on_failure" label="失败通知" valuePropName="checked">
            <Switch checkedChildren="开启" unCheckedChildren="关闭" />
          </Form.Item>

          <Form.Item name="depends_on" label="前置任务">
            <Select
              placeholder="选择前置任务（可选）"
              allowClear
              showSearch
              filterOption={(input, option) =>
                (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
              }
              options={tasks
                .filter(t => !editingTask || t.id !== editingTask.id)
                .map(t => ({
                  label: t.name,
                  value: t.id,
                }))}
            />
          </Form.Item>

          <Form.Item name="labels" label="标签">
            <Input placeholder="多个标签用英文逗号分隔" />
          </Form.Item>
        </Form>
      </Modal>
      {/* 任务详情模态框 */}
      <Modal
        title={detailTask?.name || '任务详情'}
        open={detailOpen}
        onCancel={() => setDetailOpen(false)}
        width={680}
        footer={[
          <Button key="close" onClick={() => setDetailOpen(false)}>
            关闭
          </Button>,
          <Button
            key="edit"
            icon={<EditOutlined />}
            onClick={() => { handleEdit(detailTask!); setDetailOpen(false) }}
          >
            编辑
          </Button>,
          <Button
            key="run"
            type="primary"
            icon={<CaretRightOutlined />}
            onClick={() => { handleRun(detailTask!.id); setDetailOpen(false) }}
            disabled={detailTask?.status === 2}
          >
            执行
          </Button>,
        ]}
      >
        {detailTask && (
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="任务 ID">{detailTask.id}</Descriptions.Item>
            <Descriptions.Item label="任务名称">{detailTask.name}</Descriptions.Item>
            <Descriptions.Item label="执行脚本">
              <code style={{ fontSize: 13, color: '#1677ff' }}>{detailTask.command}</code>
            </Descriptions.Item>
            <Descriptions.Item label="Cron 表达式">
              <code style={{ fontSize: 13 }}>{detailTask.cron_expression}</code>
              <div style={{ fontSize: 12, color: '#8c8c8c', marginTop: 2 }}>{describeCron(detailTask.cron_expression)}</div>
            </Descriptions.Item>
            <Descriptions.Item label="状态">
              {detailTask.status === 0 && <Tag color="default">已禁用</Tag>}
              {detailTask.status === 1 && <Tag color="processing">已启用</Tag>}
              {detailTask.status === 2 && <Tag color="warning">运行中</Tag>}
            </Descriptions.Item>
            <Descriptions.Item label="上次结果">
              {detailTask.last_run_status === null ? <Tag>未执行</Tag>
                : detailTask.last_run_status === 0 ? <Tag color="success">成功</Tag>
                : <Tag color="error">失败</Tag>}
            </Descriptions.Item>
            <Descriptions.Item label="上次执行">
              {formatUTCTime(detailTask.last_run_at)}
            </Descriptions.Item>
            <Descriptions.Item label="超时时间">{detailTask.timeout}s</Descriptions.Item>
            <Descriptions.Item label="重试次数">{detailTask.max_retries} 次</Descriptions.Item>
            <Descriptions.Item label="重试间隔">{detailTask.retry_interval}s</Descriptions.Item>
            <Descriptions.Item label="失败通知">
              <Tag color={detailTask.notify_on_failure ? 'green' : 'default'}>
                {detailTask.notify_on_failure ? '已开启' : '已关闭'}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="前置任务">
              {detailTask.depends_on ? (
                <span style={{ color: '#1677ff' }}>
                  {tasks.find(t => t.id === detailTask.depends_on)?.name || `任务 #${detailTask.depends_on}`}
                </span>
              ) : (
                <span style={{ color: '#8c8c8c' }}>无</span>
              )}
            </Descriptions.Item>
            <Descriptions.Item label="标签">
              {detailTask.labels && detailTask.labels.length > 0
                ? detailTask.labels.map(l => <Tag key={l} color="blue">{l}</Tag>)
                : <span style={{ color: '#8c8c8c' }}>无</span>}
            </Descriptions.Item>
            <Descriptions.Item label="创建时间">
              {formatUTCTime(detailTask.created_at)}
            </Descriptions.Item>
          </Descriptions>
        )}
      </Modal>

      {/* 实时日志模态框 */}
      <Modal
        title={
          <Space>
            <FileTextOutlined />
            <span>任务日志: {logTaskName}</span>
            {isHistorical && <Tag color="default">历史日志</Tag>}
            {!isHistorical && !logDone && !logError && <Tag color="processing">运行中</Tag>}
            {!isHistorical && logDone && !logError && <Tag color="success">已完成</Tag>}
          </Space>
        }
        open={logOpen}
        onCancel={handleCloseLog}
        width={800}
        footer={[
          <Button
            key="scroll"
            icon={autoScroll ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
            onClick={() => setAutoScroll(!autoScroll)}
          >
            {autoScroll ? '暂停滚动' : '继续滚动'}
          </Button>,
          <Button key="close" onClick={handleCloseLog}>
            关闭
          </Button>,
        ]}
      >
        {logError && (
          <div style={{ marginBottom: 16 }}>
            <Tag color="error">{logError}</Tag>
          </div>
        )}
        <div
          ref={logContainerRef}
          style={{
            height: '500px',
            backgroundColor: '#1e1e1e',
            borderRadius: 8,
            padding: 16,
            fontFamily: 'Consolas, Monaco, "Courier New", monospace',
            fontSize: 13,
            lineHeight: 1.6,
            overflow: 'auto',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-all',
            color: '#d4d4d4',
          }}
        >
          {logs.length === 0 ? (
            <span style={{ color: '#8c8c8c' }}>
              {logError ? logError : '等待日志输出...'}
            </span>
          ) : (
            logs.map((log, idx) => (
              <div key={idx}>
                <Ansi>{log}</Ansi>
              </div>
            ))
          )}
        </div>
      </Modal>

      {/* 日志文件列表模态框 */}
      <Modal
        title={
          <Space>
            <FolderOpenOutlined />
            <span>日志文件: {logTaskName}</span>
          </Space>
        }
        open={logFilesOpen}
        onCancel={() => setLogFilesOpen(false)}
        width={1200}
        footer={[
          <Button key="close" onClick={() => setLogFilesOpen(false)}>
            关闭
          </Button>,
        ]}
      >
        <Row gutter={16} style={{ height: '600px' }}>
          <Col span={8} style={{ height: '100%', overflowY: 'auto', borderRight: '1px solid #f0f0f0' }}>
            <div style={{ marginBottom: 8, fontWeight: 500 }}>日志文件列表</div>
            {loadingLogFiles ? (
              <div style={{ textAlign: 'center', padding: 20 }}>加载中...</div>
            ) : logFiles.length === 0 ? (
              <div style={{ textAlign: 'center', padding: 20, color: '#8c8c8c' }}>暂无日志文件</div>
            ) : (
              <List
                size="small"
                dataSource={logFiles}
                renderItem={(item: any) => (
                  <List.Item
                    style={{
                      cursor: 'pointer',
                      backgroundColor: selectedLogFile === item.filename ? '#e6f7ff' : 'transparent',
                      padding: '8px 12px',
                      borderRadius: 4,
                    }}
                    onClick={() => handleSelectLogFile(item.filename)}
                    actions={[
                      <Tooltip title="下载">
                        <Button
                          type="text"
                          size="small"
                          icon={<DownloadOutlined />}
                          onClick={(e) => {
                            e.stopPropagation()
                            handleDownloadLogFile(item.filename)
                          }}
                        />
                      </Tooltip>,
                      <Popconfirm
                        title="确定删除该日志文件？"
                        onConfirm={(e) => {
                          e?.stopPropagation()
                          handleDeleteLogFile(item.filename)
                        }}
                        onCancel={(e) => e?.stopPropagation()}
                      >
                        <Tooltip title="删除">
                          <Button
                            type="text"
                            size="small"
                            icon={<DeleteOutlined />}
                            danger
                            onClick={(e) => e.stopPropagation()}
                          />
                        </Tooltip>
                      </Popconfirm>,
                    ]}
                  >
                    <List.Item.Meta
                      title={<span style={{ fontSize: 13 }}>{item.filename}</span>}
                      description={
                        <Space size={8} style={{ fontSize: 12 }}>
                          <span>{(item.size / 1024).toFixed(1)} KB</span>
                          <span>{formatUTCTime(item.created_at)}</span>
                        </Space>
                      }
                    />
                  </List.Item>
                )}
              />
            )}
          </Col>
          <Col span={16} style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <div style={{ marginBottom: 8, fontWeight: 500 }}>
              {selectedLogFile ? `日志内容: ${selectedLogFile}` : '请选择日志文件'}
            </div>
            <div
              style={{
                flex: 1,
                backgroundColor: '#1e1e1e',
                borderRadius: 8,
                padding: 16,
                fontFamily: 'Consolas, Monaco, "Courier New", monospace',
                fontSize: 13,
                lineHeight: 1.6,
                overflow: 'auto',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-all',
                color: '#d4d4d4',
              }}
            >
              {loadingLogContent ? (
                <span style={{ color: '#8c8c8c' }}>加载中...</span>
              ) : !selectedLogFile ? (
                <span style={{ color: '#8c8c8c' }}>请从左侧选择日志文件</span>
              ) : logFileContent ? (
                logFileContent.split('\n').map((line, idx) => (
                  <div key={idx}>
                    <Ansi>{line}</Ansi>
                  </div>
                ))
              ) : (
                <span style={{ color: '#8c8c8c' }}>日志文件为空</span>
              )}
            </div>
          </Col>
        </Row>
      </Modal>
    </div>
  )
}
