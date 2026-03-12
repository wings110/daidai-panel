import { useEffect, useState, useRef } from 'react'

/**
 * 脚本运行状态
 */
export type ScriptRunStatus = 'running' | 'success' | 'failed' | 'stopped'

/**
 * 使用轮询获取脚本调试日志
 * @param runId 运行ID
 * @param enabled 是否启用（默认true）
 */
export function useScriptDebugLogs(runId: string | null, enabled: boolean = true) {
  const [logs, setLogs] = useState<string[]>([])
  const [done, setDone] = useState(false)
  const [status, setStatus] = useState<ScriptRunStatus>('running')
  const [exitCode, setExitCode] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const intervalRef = useRef<NodeJS.Timeout | null>(null)
  const retryCountRef = useRef(0)

  useEffect(() => {
    // 重置所有状态
    setLogs([])
    setDone(false)
    setStatus('running')
    setExitCode(null)
    setError(null)

    if (!enabled || !runId) {
      return
    }

    // 重置重试计数
    retryCountRef.current = 0

    const fetchLogs = async () => {
      try {
        const token = localStorage.getItem('access_token')
        const res = await fetch(`/api/scripts/run/${runId}/logs`, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        })

        if (!res.ok) {
          // 如果是 404 且重试次数少于 10 次（5秒内），不报错，继续重试
          if (res.status === 404 && retryCountRef.current < 10) {
            retryCountRef.current++
            console.log(`[Debug] 运行记录未找到，重试 ${retryCountRef.current}/10`)
            return
          }
          throw new Error('获取日志失败')
        }

        // 请求成功，重置重试计数
        retryCountRef.current = 0

        const data = await res.json()
        console.log(`[Debug] 获取日志成功，日志行数: ${data.logs?.length || 0}, 状态: ${data.status}, 完成: ${data.done}`)

        setLogs(data.logs || [])
        setDone(data.done)
        setStatus(data.status || 'running')
        setExitCode(data.exit_code)

        // 如果完成，停止轮询
        if (data.done && intervalRef.current) {
          console.log('[Debug] 脚本执行完成，停止轮询')
          clearInterval(intervalRef.current)
          intervalRef.current = null
        }
      } catch (err: any) {
        // 只有在重试次数超过限制后才设置错误
        if (retryCountRef.current >= 10) {
          console.error('[Debug] 获取日志失败:', err)
          setError(err.message || '获取日志失败')
          if (intervalRef.current) {
            clearInterval(intervalRef.current)
            intervalRef.current = null
          }
        }
      }
    }

    // 延迟 100ms 后开始第一次请求，给后端时间创建运行记录
    const initialTimeout = setTimeout(() => {
      fetchLogs()
      // 每500ms轮询一次
      intervalRef.current = setInterval(fetchLogs, 500)
    }, 100)

    // 清理函数
    return () => {
      clearTimeout(initialTimeout)
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
  }, [runId, enabled])

  return { logs, done, status, exitCode, error }
}
