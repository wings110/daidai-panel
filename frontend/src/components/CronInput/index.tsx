import { useState, useEffect, useMemo } from 'react'
import { Input, Popover, Tabs, Select, Space, Tag, Button, InputNumber } from 'antd'
import { ScheduleOutlined, FieldTimeOutlined } from '@ant-design/icons'

interface CronInputProps {
  value?: string
  onChange?: (value: string) => void
}

// Cron 预设模板
const PRESETS = [
  { label: '每分钟', cron: '* * * * *' },
  { label: '每 5 分钟', cron: '*/5 * * * *' },
  { label: '每 10 分钟', cron: '*/10 * * * *' },
  { label: '每 30 分钟', cron: '*/30 * * * *' },
  { label: '每小时', cron: '0 * * * *' },
  { label: '每 2 小时', cron: '0 */2 * * *' },
  { label: '每 6 小时', cron: '0 */6 * * *' },
  { label: '每天 0 点', cron: '0 0 * * *' },
  { label: '每天 6 点', cron: '0 6 * * *' },
  { label: '每天 9 点', cron: '0 9 * * *' },
  { label: '每天 12 点', cron: '0 12 * * *' },
  { label: '每天 18 点', cron: '0 18 * * *' },
  { label: '每周一 9 点', cron: '0 9 * * 1' },
  { label: '每月 1 号 0 点', cron: '0 0 1 * *' },
]

const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六']

/** 将 Cron 表达式解析为人类可读描述 */
function describeCron(cron: string): string {
  if (!cron) return ''
  const parts = cron.trim().split(/\s+/)
  if (parts.length < 5) return '无效表达式'

  const [minute, hour, day, month, weekday] = parts

  const segments: string[] = []

  // 月
  if (month !== '*') {
    segments.push(`${month} 月`)
  }

  // 星期
  if (weekday !== '*') {
    const dayNames = weekday.split(',').map(d => {
      const n = parseInt(d)
      return isNaN(n) ? d : `周${WEEKDAYS[n] || d}`
    }).join('、')
    segments.push(dayNames)
  }

  // 日
  if (day !== '*') {
    if (day.startsWith('*/')) {
      segments.push(`每 ${day.slice(2)} 天`)
    } else {
      segments.push(`${day} 号`)
    }
  }

  // 小时
  if (hour === '*') {
    segments.push('每小时')
  } else if (hour.startsWith('*/')) {
    segments.push(`每 ${hour.slice(2)} 小时`)
  } else {
    // 具体小时不需要额外描述，会在分钟里合并
  }

  // 分钟
  if (minute === '*' && hour === '*') {
    return '每分钟'
  } else if (minute.startsWith('*/')) {
    segments.push(`每 ${minute.slice(2)} 分钟`)
  } else if (hour !== '*' && !hour.startsWith('*/')) {
    segments.push(`${hour.padStart(2, '0')}:${minute.padStart(2, '0')}`)
  } else {
    segments.push(`第 ${minute} 分`)
  }

  return segments.join(' ') || cron
}

/** 自定义选择器 Tab */
function CustomBuilder({
  value,
  onChange,
}: {
  value: string
  onChange: (v: string) => void
}) {
  const parts = value.trim().split(/\s+/)
  const [minute, setMinute] = useState(parts[0] || '0')
  const [hour, setHour] = useState(parts[1] || '*')
  const [day, setDay] = useState(parts[2] || '*')
  const [month, setMonth] = useState(parts[3] || '*')
  const [weekday, setWeekday] = useState(parts[4] || '*')

  useEffect(() => {
    const p = value.trim().split(/\s+/)
    if (p.length >= 5) {
      setMinute(p[0])
      setHour(p[1])
      setDay(p[2])
      setMonth(p[3])
      setWeekday(p[4])
    }
  }, [value])

  const apply = () => {
    onChange(`${minute} ${hour} ${day} ${month} ${weekday}`)
  }

  const hourOptions = [
    { label: '每小时 (*)', value: '*' },
    ...Array.from({ length: 24 }, (_, i) => ({
      label: `${i} 时`,
      value: String(i),
    })),
  ]

  const minuteOptions = [
    { label: '每分钟 (*)', value: '*' },
    { label: '每 5 分钟', value: '*/5' },
    { label: '每 10 分钟', value: '*/10' },
    { label: '每 15 分钟', value: '*/15' },
    { label: '每 30 分钟', value: '*/30' },
    ...Array.from({ length: 60 }, (_, i) => ({
      label: `${i} 分`,
      value: String(i),
    })),
  ]

  const weekdayOptions = [
    { label: '不限 (*)', value: '*' },
    ...WEEKDAYS.map((name, i) => ({
      label: `周${name}`,
      value: String(i),
    })),
  ]

  return (
    <div style={{ width: 320 }}>
      <Space direction="vertical" style={{ width: '100%' }} size={8}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ width: 40, fontSize: 13 }}>分钟</span>
          <Select
            size="small"
            value={minute}
            onChange={setMinute}
            options={minuteOptions}
            style={{ flex: 1 }}
            showSearch
          />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ width: 40, fontSize: 13 }}>小时</span>
          <Select
            size="small"
            value={hour}
            onChange={setHour}
            options={hourOptions}
            style={{ flex: 1 }}
            showSearch
          />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ width: 40, fontSize: 13 }}>日期</span>
          <Input
            size="small"
            value={day}
            onChange={e => setDay(e.target.value)}
            placeholder="* 或 1-31"
            style={{ flex: 1 }}
          />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ width: 40, fontSize: 13 }}>月份</span>
          <Input
            size="small"
            value={month}
            onChange={e => setMonth(e.target.value)}
            placeholder="* 或 1-12"
            style={{ flex: 1 }}
          />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ width: 40, fontSize: 13 }}>星期</span>
          <Select
            size="small"
            value={weekday}
            onChange={setWeekday}
            options={weekdayOptions}
            style={{ flex: 1 }}
          />
        </div>
        <Button type="primary" size="small" block onClick={apply}>
          应用
        </Button>
      </Space>
    </div>
  )
}

export default function CronInput({ value = '', onChange }: CronInputProps) {
  const [open, setOpen] = useState(false)

  const description = useMemo(() => describeCron(value), [value])

  const handleSelect = (cron: string) => {
    onChange?.(cron)
    setOpen(false)
  }

  const content = (
    <div style={{ width: 340 }}>
      <Tabs
        size="small"
        items={[
          {
            key: 'presets',
            label: '快捷选择',
            children: (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {PRESETS.map(p => (
                  <Tag
                    key={p.cron}
                    style={{ cursor: 'pointer', margin: 0 }}
                    color={value === p.cron ? 'blue' : undefined}
                    onClick={() => handleSelect(p.cron)}
                  >
                    {p.label}
                  </Tag>
                ))}
              </div>
            ),
          },
          {
            key: 'custom',
            label: '自定义',
            children: (
              <CustomBuilder
                value={value || '0 * * * *'}
                onChange={handleSelect}
              />
            ),
          },
        ]}
      />
    </div>
  )

  return (
    <div>
      <Popover
        content={content}
        trigger="click"
        open={open}
        onOpenChange={setOpen}
        placement="bottomLeft"
      >
        <Input
          value={value}
          onChange={e => onChange?.(e.target.value)}
          placeholder="0 9 * * *"
          suffix={
            <ScheduleOutlined
              style={{ color: '#8c8c8c', cursor: 'pointer' }}
            />
          }
        />
      </Popover>
      {description && (
        <div style={{ marginTop: 4, fontSize: 12, color: '#8c8c8c' }}>
          <FieldTimeOutlined style={{ marginRight: 4 }} />
          {description}
        </div>
      )}
    </div>
  )
}

export { describeCron }
