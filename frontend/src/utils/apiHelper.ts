import { message } from 'antd'

/**
 * 统一的错误处理函数
 * @param error 错误对象
 * @param defaultMessage 默认错误消息
 */
export function handleApiError(error: any, defaultMessage: string = '操作失败，请稍后重试') {
  // 从响应中提取错误消息
  const errorMsg = error?.response?.data?.error || error?.message || defaultMessage

  // 显示错误提示
  message.error(errorMsg)

  // 返回错误消息，方便调用方使用
  return errorMsg
}

/**
 * 统一的成功提示函数
 * @param msg 成功消息
 * @param data 响应数据（可选）
 */
export function handleApiSuccess(msg: string, data?: any) {
  message.success(msg)
  return data
}

/**
 * 从API响应中提取数据
 * @param response API响应
 */
export function extractApiData<T = any>(response: any): T {
  return response?.data?.data || response?.data
}

/**
 * 检查API响应是否成功
 * @param response API响应
 */
export function isApiSuccess(response: any): boolean {
  return response?.data?.success !== false && response?.status >= 200 && response?.status < 300
}
