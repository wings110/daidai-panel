import { useEffect, useState, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Row, Col, Card, Statistic, Table, Tag, Typography, Space, Button, message, Tooltip } from 'antd'
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  PauseCircleOutlined,
  ThunderboltOutlined,
  FileTextOutlined,
  CodeOutlined,
  KeyOutlined,
  CloudDownloadOutlined,
  ArrowRightOutlined,
  PlayCircleOutlined,
  DashboardOutlined,
} from '@ant-design/icons'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RTooltip,
  ResponsiveContainer, Legend, PieChart, Pie, Cell,
  AreaChart, Area, BarChart, Bar,
} from 'recharts'
import { logApi, systemApi, taskApi } from '../../services/api'
import dayjs from 'dayjs'
import { formatUTCTime, formatTimestampMs } from '../../utils/timeHelper'

const { Title, Text } = Typography

interface Stats {
  tasks: { total: number; enabled: number; disabled: number; running: number }
  logs: { total: number; success: number; failed: number; success_rate: number }
  today_logs: number
  env_count: number
  sub_count: number
  scripts_count: number
}

interface TrendItem {
  date: string
  total: number
  success: number
  failed: number
}

interface LogRecord {
  id: number
  task_name: string
  status: number
  duration: number
  started_at: string
}

interface ResourcePoint {
  time: string
  cpu: number
  memory: number
}

interface QuickTask {
  id: number
  name: string
  status: number
  last_run_status: number | null
}

interface DurationStat {
  task_id: number
  task_name: string
  avg_duration: number
  exec_count: number
}

interface SuccessRateStat {
  task_id: number
  task_name: string
  total: number
  success: number
  success_rate: number
}

const PIE_COLORS = ['#52c41a', '#ff4d4f', '#faad14', '#d9d9d9']

export default function Dashboard() {
  const navigate = useNavigate()
  const [stats, setStats] = useState<Stats | null>(null)
  const [trend, setTrend] = useState<TrendItem[]>([])
  const [recentLogs, setRecentLogs] = useState<LogRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [resourceData, setResourceData] = useState<ResourcePoint[]>([])
  const [quickTasks, setQuickTasks] = useState<QuickTask[]>([])
  const [runningTaskId, setRunningTaskId] = useState<number | null>(null)
  const [durationStats, setDurationStats] = useState<DurationStat[]>([])
  const [successRateStats, setSuccessRateStats] = useState<SuccessRateStat[]>([])
  const eventSourceRef = useRef<EventSource | null>(null)

  useEffect(() => {
    fetchData()
    fetchQuickTasks()
    connectResourceStream()
    return () => {
      eventSourceRef.current?.close()
    }
  }, [])

  const connectResourceStream = useCallback(() => {
    const token = localStorage.getItem('access_token')
    const es = new EventSource(`/api/system/resource-stream?token=${token}`)
    eventSourceRef.current = es
    es.onmessage = (event) => {
      try {
        const d = JSON.parse(event.data)
        const point: ResourcePoint = {
          time: formatTimestampMs(d.ts * 1000, 'HH:mm:ss'),
          cpu: d.cpu,
          memory: d.memory,
        }
        setResourceData(prev => {
          const next = [...prev, point]
          return next.length > 60 ? next.slice(-60) : next
        })
      } catch { /* ignore */ }
    }
    es.onerror = () => {
      es.close()
      setTimeout(connectResourceStream, 5000)
    }
  }, [])

  const fetchQuickTasks = async () => {
    try {
      const res = await taskApi.list({ status: 1, page_size: 6 })
      setQuickTasks((res.data.data || []).slice(0, 6))
    } catch { /* ignore */ }
  }

  const handleQuickRun = async (taskId: number) => {
    setRunningTaskId(taskId)
    try {
      await taskApi.run(taskId)
      message.success('任务已触发执行')
    } catch {
      message.error('执行失败')
    } finally {
      setRunningTaskId(null)
    }
  }

  const fetchData = async () => {
    setLoading(true)
    try {
      const [statsRes, trendRes, logsRes, durationRes, successRateRes] = await Promise.all([
        systemApi.getStats(),
        systemApi.getTrend(),
        logApi.list({ page: 1, page_size: 10 }),
        systemApi.getDurationStats(),
        systemApi.getSuccessRateStats(),
      ])
      setStats(statsRes.data.data)
      setTrend(trendRes.data.data || [])
      setRecentLogs(logsRes.data.data || [])
      setDurationStats(durationRes.data.data || [])
      setSuccessRateStats(successRateRes.data.data || [])
    } catch {
      // 静默处理
    } finally {
      setLoading(false)
    }
  }

  const pieData = stats ? [
    { name: '执行成功', value: stats.logs.success },
    { name: '执行失败', value: stats.logs.failed },
  ].filter(d => d.value > 0) : []

  const totalLogCount = stats ? stats.logs.total : 0

  // 统计卡片配置
  const statCards = stats ? [
    {
      title: '今日执行', value: stats.today_logs, icon: <ThunderboltOutlined />,
      color: '#fa541c', bg: 'linear-gradient(135deg, #fff2e8, #fff7e6)',
      link: '/logs',
    },
    {
      title: '任务总数', value: stats.tasks.total, icon: <ClockCircleOutlined />,
      color: '#1677ff', bg: 'linear-gradient(135deg, #e6f4ff, #f0f5ff)',
      link: '/tasks',
    },
    {
      title: '环境变量', value: stats.env_count, icon: <KeyOutlined />,
      color: '#52c41a', bg: 'linear-gradient(135deg, #f6ffed, #fcffe6)',
      link: '/envs',
    },
    {
      title: '日志总数', value: stats.logs.total, icon: <FileTextOutlined />,
      color: '#722ed1', bg: 'linear-gradient(135deg, #f9f0ff, #efdbff)',
      link: '/logs',
    },
    {
      title: '订阅数量', value: stats.sub_count, icon: <CloudDownloadOutlined />,
      color: '#13c2c2', bg: 'linear-gradient(135deg, #e6fffb, #b5f5ec)',
      link: '/subscriptions',
    },
    {
      title: '正在运行', value: stats.tasks.running, icon: <ThunderboltOutlined />,
      color: '#faad14', bg: 'linear-gradient(135deg, #fffbe6, #fff1b8)',
      link: '/tasks',
    },
  ] : []

  const logColumns = [
    {
      title: '任务名称',
      dataIndex: 'task_name',
      key: 'task_name',
      ellipsis: true,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (status: number) =>
        status === 0 ? (
          <Tag color="success" icon={<CheckCircleOutlined />}>成功</Tag>
        ) : (
          <Tag color="error" icon={<CloseCircleOutlined />}>失败</Tag>
        ),
    },
    {
      title: '耗时',
      dataIndex: 'duration',
      key: 'duration',
      width: 100,
      render: (v: number) => (v != null ? `${v.toFixed(1)}s` : '-'),
    },
    {
      title: '执行时间',
      dataIndex: 'started_at',
      key: 'started_at',
      width: 170,
      render: (v: string) => formatUTCTime(v, 'MM-DD HH:mm:ss'),
    },
  ]

  return (
    <div className="animate-fade-in">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <Title level={4} style={{ margin: 0, fontWeight: 600 }}>数据仪表</Title>
          <Text type="secondary" style={{ fontSize: 13 }}>查看系统运行状态和统计数据</Text>
        </div>
      </div>

      {/* 6个统计卡片 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        {statCards.map((card, i) => (
          <Col xs={12} sm={8} md={4} key={card.title}>
            <Card
              hoverable
              className="card-hover animate-fade-in-up"
              style={{
                borderRadius: 10, cursor: 'pointer',
                background: card.bg, border: 'none',
                animationDelay: `${i * 0.06}s`,
              }}
              styles={{ body: { padding: '16px 20px' } }}
              onClick={() => navigate(card.link)}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <div style={{ fontSize: 13, color: '#8c8c8c', marginBottom: 8 }}>{card.title}</div>
                  <div style={{ fontSize: 28, fontWeight: 700, color: card.color, lineHeight: 1.2 }}>
                    {card.value}
                  </div>
                </div>
                <div style={{
                  fontSize: 20, color: card.color, opacity: 0.5,
                  display: 'flex', alignItems: 'center', gap: 4,
                }}>
                  {card.icon}
                  <ArrowRightOutlined style={{ fontSize: 12 }} />
                </div>
              </div>
            </Card>
          </Col>
        ))}
      </Row>

      {/* 图表区域 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        {/* 执行统计折线图 */}
        <Col xs={24} lg={16}>
          <Card
            className="card-hover animate-fade-in-up"
            style={{ borderRadius: 10, animationDelay: '0.35s' }}
            title={
              <Space>
                <span style={{ width: 3, height: 14, borderRadius: 2, background: '#1677ff', display: 'inline-block' }} />
                <span style={{ fontWeight: 600 }}>执行统计</span>
                <Text type="secondary" style={{ fontSize: 12, fontWeight: 400 }}>最近30天任务执行情况</Text>
              </Space>
            }
          >
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={trend} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis
                  dataKey="date"
                  tickFormatter={(v: string) => v.slice(5)}
                  tick={{ fontSize: 11, fill: '#8c8c8c' }}
                  axisLine={{ stroke: '#f0f0f0' }}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: '#8c8c8c' }}
                  axisLine={{ stroke: '#f0f0f0' }}
                  allowDecimals={false}
                />
                <RTooltip
                  contentStyle={{
                    borderRadius: 8, border: '1px solid #f0f0f0',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
                  }}
                  labelFormatter={(v) => `日期: ${v}`}
                />
                <Legend
                  iconType="circle"
                  iconSize={8}
                  wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
                />
                <Line
                  type="monotone" dataKey="total" name="执行总数"
                  stroke="#1677ff" strokeWidth={2}
                  dot={{ r: 3, fill: '#1677ff' }} activeDot={{ r: 5 }}
                />
                <Line
                  type="monotone" dataKey="success" name="执行成功"
                  stroke="#52c41a" strokeWidth={2}
                  dot={{ r: 3, fill: '#52c41a' }} activeDot={{ r: 5 }}
                />
                <Line
                  type="monotone" dataKey="failed" name="执行失败"
                  stroke="#ff4d4f" strokeWidth={2}
                  dot={{ r: 3, fill: '#ff4d4f' }} activeDot={{ r: 5 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </Card>
        </Col>

        {/* 任务占比饼图 */}
        <Col xs={24} lg={8}>
          <Card
            className="card-hover animate-fade-in-up"
            style={{ borderRadius: 10, animationDelay: '0.4s' }}
            title={
              <Space>
                <span style={{ width: 3, height: 14, borderRadius: 2, background: '#52c41a', display: 'inline-block' }} />
                <span style={{ fontWeight: 600 }}>任务占比</span>
                <Text type="secondary" style={{ fontSize: 12, fontWeight: 400 }}>最近30天执行分布</Text>
              </Space>
            }
          >
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%" cy="45%"
                  innerRadius={60} outerRadius={90}
                  paddingAngle={3}
                  dataKey="value"
                  label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(1)}%`}
                  labelLine={{ stroke: '#d9d9d9' }}
                >
                  {pieData.map((_entry, index) => (
                    <Cell key={index} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <RTooltip
                  contentStyle={{ borderRadius: 8, border: '1px solid #f0f0f0' }}
                  formatter={(value) => [`${value} 次`, '']}
                />
                <text
                  x="50%" y="43%" textAnchor="middle" dominantBaseline="central"
                  style={{ fontSize: 12, fill: '#8c8c8c' }}
                >
                  总执行
                </text>
                <text
                  x="50%" y="50%" textAnchor="middle" dominantBaseline="central"
                  style={{ fontSize: 20, fontWeight: 700, fill: '#1f1f1f' }}
                >
                  {totalLogCount}次
                </text>
              </PieChart>
            </ResponsiveContainer>
          </Card>
        </Col>
      </Row>

      {/* 系统资源实时监控 + 快捷操作 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} lg={16}>
          <Card
            className="card-hover animate-fade-in-up"
            style={{ borderRadius: 10, animationDelay: '0.5s' }}
            title={
              <Space>
                <span style={{ width: 3, height: 14, borderRadius: 2, background: '#fa541c', display: 'inline-block' }} />
                <span style={{ fontWeight: 600 }}>系统资源</span>
                <Text type="secondary" style={{ fontSize: 12, fontWeight: 400 }}>实时 CPU / 内存使用率</Text>
              </Space>
            }
          >
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={resourceData} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#8c8c8c' }} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: '#8c8c8c' }} unit="%" />
                <RTooltip contentStyle={{ borderRadius: 8, border: '1px solid #f0f0f0' }} />
                <Area type="monotone" dataKey="cpu" name="CPU" stroke="#fa541c" fill="#fa541c" fillOpacity={0.15} strokeWidth={2} />
                <Area type="monotone" dataKey="memory" name="内存" stroke="#1677ff" fill="#1677ff" fillOpacity={0.15} strokeWidth={2} />
                <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12 }} />
              </AreaChart>
            </ResponsiveContainer>
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card
            className="card-hover animate-fade-in-up"
            style={{ borderRadius: 10, animationDelay: '0.55s' }}
            title={
              <Space>
                <span style={{ width: 3, height: 14, borderRadius: 2, background: '#13c2c2', display: 'inline-block' }} />
                <span style={{ fontWeight: 600 }}>快捷操作</span>
                <Text type="secondary" style={{ fontSize: 12, fontWeight: 400 }}>一键执行常用任务</Text>
              </Space>
            }
          >
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {quickTasks.length === 0 && <Text type="secondary">暂无已启用任务</Text>}
              {quickTasks.map(t => (
                <div key={t.id} style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '8px 12px', borderRadius: 8, background: '#fafafa',
                }}>
                  <Text ellipsis style={{ flex: 1, fontSize: 13 }}>{t.name}</Text>
                  <Tooltip title="立即执行">
                    <Button
                      type="primary"
                      size="small"
                      icon={<PlayCircleOutlined />}
                      loading={runningTaskId === t.id}
                      onClick={() => handleQuickRun(t.id)}
                    >
                      执行
                    </Button>
                  </Tooltip>
                </div>
              ))}
            </div>
          </Card>
        </Col>
      </Row>

      {/* 最近执行记录 */}
      <Card
        title={
          <Space>
            <span style={{ width: 3, height: 14, borderRadius: 2, background: '#722ed1', display: 'inline-block' }} />
            <span style={{ fontWeight: 600 }}>最近执行记录</span>
          </Space>
        }
        className="animate-fade-in-up"
        style={{ borderRadius: 10, animationDelay: '0.6s', marginBottom: 24 }}
        styles={{ body: { padding: 0 } }}
        extra={
          <a onClick={() => navigate('/logs')} style={{ fontSize: 13 }}>
            查看全部 <ArrowRightOutlined />
          </a>
        }
      >
        <Table
          dataSource={recentLogs}
          columns={logColumns}
          rowKey="id"
          loading={loading}
          pagination={false}
          size="middle"
          locale={{ emptyText: '暂无执行记录' }}
        />
      </Card>

      {/* 任务执行时长统计 + 成功率统计 */}
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card
            className="card-hover animate-fade-in-up"
            style={{ borderRadius: 10, animationDelay: '0.65s' }}
            title={
              <Space>
                <span style={{ width: 3, height: 14, borderRadius: 2, background: '#faad14', display: 'inline-block' }} />
                <span style={{ fontWeight: 600 }}>任务执行时长</span>
                <Text type="secondary" style={{ fontSize: 12, fontWeight: 400 }}>平均耗时 Top 10</Text>
              </Space>
            }
          >
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={durationStats} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis
                  dataKey="task_name"
                  tick={{ fontSize: 11, fill: '#8c8c8c' }}
                  angle={-15}
                  textAnchor="end"
                  height={80}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: '#8c8c8c' }}
                  label={{ value: '秒', angle: -90, position: 'insideLeft', style: { fontSize: 11 } }}
                />
                <RTooltip
                  contentStyle={{ borderRadius: 8, border: '1px solid #f0f0f0' }}
                  formatter={(value: any, name: any) => {
                    if (value === undefined || value === null) return ['', name || '']
                    const numValue = typeof value === 'number' ? value : parseFloat(value)
                    if (isNaN(numValue)) return [value, name]
                    if (name === 'avg_duration') return [`${numValue.toFixed(2)}秒`, '平均耗时']
                    if (name === 'exec_count') return [`${numValue}次`, '执行次数']
                    return [value, name]
                  }}
                />
                <Legend
                  iconType="circle"
                  iconSize={8}
                  wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
                />
                <Bar dataKey="avg_duration" name="平均耗时" fill="#faad14" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card
            className="card-hover animate-fade-in-up"
            style={{ borderRadius: 10, animationDelay: '0.7s' }}
            title={
              <Space>
                <span style={{ width: 3, height: 14, borderRadius: 2, background: '#52c41a', display: 'inline-block' }} />
                <span style={{ fontWeight: 600 }}>任务成功率</span>
                <Text type="secondary" style={{ fontSize: 12, fontWeight: 400 }}>执行次数 Top 10</Text>
              </Space>
            }
          >
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={successRateStats} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis
                  dataKey="task_name"
                  tick={{ fontSize: 11, fill: '#8c8c8c' }}
                  angle={-15}
                  textAnchor="end"
                  height={80}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: '#8c8c8c' }}
                  label={{ value: '%', angle: -90, position: 'insideLeft', style: { fontSize: 11 } }}
                  domain={[0, 100]}
                />
                <RTooltip
                  contentStyle={{ borderRadius: 8, border: '1px solid #f0f0f0' }}
                  formatter={(value: any, name: any) => {
                    if (value === undefined || value === null) return ['', name || '']
                    const numValue = typeof value === 'number' ? value : parseFloat(value)
                    if (isNaN(numValue)) return [value, name]
                    if (name === 'success_rate') return [`${numValue}%`, '成功率']
                    if (name === 'total') return [`${numValue}次`, '总执行']
                    if (name === 'success') return [`${numValue}次`, '成功次数']
                    return [value, name]
                  }}
                />
                <Legend
                  iconType="circle"
                  iconSize={8}
                  wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
                />
                <Bar dataKey="success_rate" name="成功率" fill="#52c41a" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
