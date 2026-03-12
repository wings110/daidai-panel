import dayjs from 'dayjs'
import utc from 'dayjs/plugin/utc'
import timezone from 'dayjs/plugin/timezone'

// 启用 UTC 和时区插件
dayjs.extend(utc)
dayjs.extend(timezone)

/**
 * 将 UTC 时间字符串转换为本地时间并格式化
 * @param utcTime UTC 时间字符串（ISO 8601 格式）
 * @param format 格式化字符串，默认 'YYYY-MM-DD HH:mm:ss'
 * @returns 格式化后的本地时间字符串
 */
export function formatUTCTime(utcTime: string | null | undefined, format: string = 'YYYY-MM-DD HH:mm:ss'): string {
  if (!utcTime) return '-'
  return dayjs.utc(utcTime).local().format(format)
}

/**
 * 将 Unix 时间戳（秒）转换为本地时间并格式化
 * @param timestamp Unix 时间戳（秒）
 * @param format 格式化字符串，默认 'YYYY-MM-DD HH:mm:ss'
 * @returns 格式化后的本地时间字符串
 */
export function formatTimestamp(timestamp: number | null | undefined, format: string = 'YYYY-MM-DD HH:mm:ss'): string {
  if (!timestamp) return '-'
  return dayjs.unix(timestamp).format(format)
}

/**
 * 将 Unix 时间戳（毫秒）转换为本地时间并格式化
 * @param timestamp Unix 时间戳（毫秒）
 * @param format 格式化字符串，默认 'YYYY-MM-DD HH:mm:ss'
 * @returns 格式化后的本地时间字符串
 */
export function formatTimestampMs(timestamp: number | null | undefined, format: string = 'YYYY-MM-DD HH:mm:ss'): string {
  if (!timestamp) return '-'
  return dayjs(timestamp).format(format)
}

/**
 * 获取当前本地时间
 * @param format 格式化字符串，默认 'YYYY-MM-DD HH:mm:ss'
 * @returns 格式化后的当前时间字符串
 */
export function getCurrentTime(format: string = 'YYYY-MM-DD HH:mm:ss'): string {
  return dayjs().format(format)
}

/**
 * 计算相对时间（多久之前）
 * @param utcTime UTC 时间字符串
 * @returns 相对时间描述，如 "2小时前"
 */
export function getRelativeTime(utcTime: string | null | undefined): string {
  if (!utcTime) return '-'
  const now = dayjs()
  const time = dayjs.utc(utcTime).local()
  const diffMinutes = now.diff(time, 'minute')
  const diffHours = now.diff(time, 'hour')
  const diffDays = now.diff(time, 'day')

  if (diffMinutes < 1) return '刚刚'
  if (diffMinutes < 60) return `${diffMinutes}分钟前`
  if (diffHours < 24) return `${diffHours}小时前`
  if (diffDays < 7) return `${diffDays}天前`
  return time.format('YYYY-MM-DD HH:mm')
}
