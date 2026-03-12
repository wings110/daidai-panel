import { useEffect, useState, useRef } from 'react'
import { taskApi, logApi } from '../services/api'

/**
 * 获取任务日志（实时或历史）
 *
 * 逻辑：
 * 1. 先调用 getLatestLog 获取最新日志记录
 * 2. 如果任务正在运行（status === 2），尝试 SSE 实时日志
 * 3. 如果任务不在运行，直接显示历史日志内容
 * 4. 如果无日志记录，显示"暂无日志记录"
 * 5. 如果日志文件已被清理（content 为空），显示"日志已过期"
 */
export function useTaskLiveLogs(taskId: number | null, enabled: boolean = true) {
  const [logs, setLogs] = useState<string[]>([])
  const [done, setDone] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isHistorical, setIsHistorical] = useState(false)
  const [logId, setLogId] = useState<number | null>(null)
  const esRef = useRef<EventSource | null>(null)
  const pollingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const cancelledRef = useRef(false)

  useEffect(() => {
    if (!enabled || !taskId) {
      return
    }

    // 重置状态
    setLogs([])
    setDone(false)
    setError(null)
    setIsHistorical(false)
    setLogId(null)
    cancelledRef.current = false

    const token = localStorage.getItem('access_token')
    if (!token) {
      setError('未登录')
      return
    }

    // 连接SSE获取实时日志（仅在任务运行中时调用）
    const connectSSE = () => {
      if (cancelledRef.current) return

      const es = new EventSource(`/api/logs/${taskId}/stream?token=${token}`)
      esRef.current = es
      let hasReceivedData = false

      es.onmessage = (e) => {
        hasReceivedData = true
        setLogs(prev => [...prev, e.data])
      }

      es.addEventListener('done', () => {
        es.close()
        esRef.current = null
        setDone(true)
        // SSE 结束但没收到数据，可能是日志缓冲已清理，尝试从文件读取
        if (!hasReceivedData) {
          fetchHistoricalLog()
        }
      })

      es.onerror = () => {
        es.close()
        esRef.current = null
        // SSE 连接失败，回退到轮询
        startPollingRunningLog()
      }
    }

    // 轮询运行中任务的日志（SSE 失败时的回退）
    const startPollingRunningLog = async () => {
      if (cancelledRef.current) return
      try {
        const res = await taskApi.getLatestLog(taskId)
        const logData = res.data.data
        if (logData && logData.content) {
          setLogs(logData.content.split('\n').filter((line: string) => line !== ''))
          setLogId(logData.id)
        }
        if (logData && logData.status === 2) {
          // 任务还在运行，继续轮询
          pollingTimerRef.current = setTimeout(() => startPollingRunningLog(), 2000)
        } else {
          setDone(true)
        }
      } catch {
        setDone(true)
      }
    }

    // 获取历史日志（任务不在运行时）
    const fetchHistoricalLog = async () => {
      if (cancelledRef.current) return
      try {
        const res = await taskApi.getLatestLog(taskId)
        const logData = res.data.data
        if (logData) {
          setLogId(logData.id)
          setIsHistorical(true)
          if (logData.content) {
            setLogs(logData.content.split('\n').filter((line: string) => line !== ''))
          } else {
            // 日志记录存在但内容为空 → 文件已被清理
            setError('日志已过期，文件已被清理')
          }
        } else {
          setError('暂无日志记录')
        }
        setDone(true)
      } catch (err: any) {
        if (err?.response?.status === 404) {
          setError('暂无日志记录')
        } else {
          setError('获取日志失败')
        }
        setDone(true)
      }
    }

    // 入口：先获取最新日志判断任务状态
    const init = async () => {
      try {
        const res = await taskApi.getLatestLog(taskId)
        const logData = res.data.data

        if (cancelledRef.current) return

        if (!logData) {
          setError('暂无日志记录')
          setDone(true)
          return
        }

        if (logData.status === 2) {
          // 任务正在运行 → 尝试 SSE 实时日志
          connectSSE()
        } else {
          // 任务未运行 → 直接显示历史日志
          setLogId(logData.id)
          setIsHistorical(true)
          if (logData.content) {
            setLogs(logData.content.split('\n').filter((line: string) => line !== ''))
          } else {
            setError('日志已过期，文件已被清理')
          }
          setDone(true)
        }
      } catch (err: any) {
        if (cancelledRef.current) return
        if (err?.response?.status === 404) {
          setError('暂无日志记录')
        } else {
          setError('获取日志失败')
        }
        setDone(true)
      }
    }

    init()

    // 清理函数
    return () => {
      cancelledRef.current = true
      if (esRef.current) {
        esRef.current.close()
        esRef.current = null
      }
      if (pollingTimerRef.current) {
        clearTimeout(pollingTimerRef.current)
        pollingTimerRef.current = null
      }
    }
  }, [taskId, enabled])

  const close = () => {
    cancelledRef.current = true
    if (esRef.current) {
      esRef.current.close()
      esRef.current = null
    }
    if (pollingTimerRef.current) {
      clearTimeout(pollingTimerRef.current)
      pollingTimerRef.current = null
    }
  }

  return { logs, done, error, close, isHistorical, logId }
}
