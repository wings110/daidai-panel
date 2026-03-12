import { useState, useRef, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Form, Input, Button, message } from 'antd'
import { UserOutlined, LockOutlined, EyeOutlined, EyeInvisibleOutlined, SafetyOutlined } from '@ant-design/icons'
import { useAuthStore } from '../../stores/authStore'
import Characters, { type CharacterMood } from './Characters'
import './login.css'

// 声明极验 SDK 全局函数
declare global {
  interface Window {
    initGeetest4?: (config: any, callback: (obj: any) => void) => void
  }
}

// 动态加载极验 V4 SDK
function loadGeetestSDK(): Promise<void> {
  return new Promise((resolve, reject) => {
    if (window.initGeetest4) {
      resolve()
      return
    }
    const script = document.createElement('script')
    script.src = 'https://static.geetest.com/v4/gt4.js'
    script.onload = () => resolve()
    script.onerror = () => reject(new Error('极验 SDK 加载失败'))
    document.head.appendChild(script)
  })
}

export default function Login() {
  const [loading, setLoading] = useState(false)
  const [isInit, setIsInit] = useState(false)
  const [checkingInit, setCheckingInit] = useState(true)
  const [mood, setMood] = useState<CharacterMood>('idle')
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 })
  const [pwdVisible, setPwdVisible] = useState(false)
  const [focusField, setFocusField] = useState<'none' | 'username' | 'password' | 'totp'>('none')
  const [require2FA, setRequire2FA] = useState(false)
  const [requireCaptcha, setRequireCaptcha] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const captchaObjRef = useRef<any>(null)
  const navigate = useNavigate()
  const { login, initAdmin } = useAuthStore()
  const [form] = Form.useForm()

  // 页面加载时检查是否需要初始化
  useEffect(() => {
    const checkNeedInit = async () => {
      try {
        const res = await fetch('/api/auth/check-init')
        const data = await res.json()
        if (data.need_init) {
          setIsInit(true)
        }
      } catch {
        // 忽略错误
      } finally {
        setCheckingInit(false)
      }
    }
    checkNeedInit()
  }, [])

  // 初始化极验验证码
  const initCaptcha = useCallback(async (pendingValues: { username: string; password: string; totp_token?: string }) => {
    try {
      // 获取极验配置
      const configRes = await fetch('/api/auth/captcha-config')
      const configData = await configRes.json()

      if (!configData.enabled || !configData.captcha_id) {
        // 极验未启用，直接提示
        message.warning('验证码服务未配置，请联系管理员')
        setLoading(false)
        return
      }

      // 加载 SDK
      await loadGeetestSDK()

      // 初始化极验
      window.initGeetest4!({
        captchaId: configData.captcha_id,
        product: 'bind',
        language: 'zho',
      }, (captchaObj: any) => {
        captchaObjRef.current = captchaObj

        captchaObj.onReady(() => {
          setLoading(false)
          // 自动弹出验证码
          captchaObj.showCaptcha()
        }).onSuccess(async () => {
          const result = captchaObj.getValidate()
          if (result) {
            // 带验证码数据重新登录
            setLoading(true)
            try {
              await login(
                pendingValues.username,
                pendingValues.password,
                pendingValues.totp_token,
                {
                  lot_number: result.lot_number,
                  captcha_output: result.captcha_output,
                  pass_token: result.pass_token,
                  gen_time: result.gen_time,
                }
              )
              setMood('success')
              message.success('登录成功')
              setTimeout(() => {
                navigate('/dashboard', { replace: true })
              }, 800)
            } catch (err: any) {
              const errorData = err?.response?.data
              setMood('error')
              message.error(errorData?.error || '登录失败')
              setTimeout(() => setMood('idle'), 2000)
            } finally {
              setLoading(false)
            }
          }
        }).onError(() => {
          message.error('验证码错误，请重试')
          setLoading(false)
        })
      })
    } catch {
      message.error('验证码加载失败，请刷新重试')
      setLoading(false)
    }
  }, [login, navigate])

  // 鼠标移动跟踪
  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!containerRef.current) return
    const rect = containerRef.current.getBoundingClientRect()
    const cx = rect.left + rect.width / 2
    const cy = rect.top + rect.height / 2
    const x = Math.max(-1, Math.min(1, (e.clientX - cx) / (rect.width / 2)))
    const y = Math.max(-1, Math.min(1, (e.clientY - cy) / (rect.height / 2)))
    setMousePos({ x, y })
  }, [])

  // 输入焦点与表情联动
  const handleUsernameFocus = () => {
    setFocusField('username')
    setMood('typing')
    setPwdVisible(false)
  }

  const handlePasswordFocus = () => {
    setFocusField('password')
    if (!pwdVisible) {
      setMood('password')
    } else {
      setMood('peek')
    }
  }

  const handleBlur = () => {
    setFocusField('none')
    if (mood !== 'success' && mood !== 'error') {
      setMood('idle')
    }
  }

  // 密码可见性切换
  const togglePwdVisible = () => {
    const next = !pwdVisible
    setPwdVisible(next)
    if (focusField === 'password') {
      setMood(next ? 'peek' : 'password')
    }
  }

  // 登录/注册提交
  const handleSubmit = async (values: { username: string; password: string; totp_token?: string }) => {
    setLoading(true)
    try {
      if (isInit) {
        // 初始化管理员
        await initAdmin(values.username, values.password)
        setMood('success')
        message.success('初始化成功，正在登录...')

        // 初始化成功后自动登录
        await login(values.username, values.password)
        setTimeout(() => {
          navigate('/dashboard', { replace: true })
        }, 800)
      } else {
        // 正常登录
        await login(values.username, values.password, values.totp_token)
        setMood('success')
        message.success('登录成功')
        setTimeout(() => {
          navigate('/dashboard', { replace: true })
        }, 800)
      }
    } catch (err: any) {
      const errorData = err?.response?.data
      if (errorData?.need_init) {
        setIsInit(true)
        setMood('idle')
        message.info('首次使用，请初始化管理员账号')
      } else if (errorData?.require_2fa) {
        // 需要2FA验证
        setRequire2FA(true)
        setMood('idle')
        message.info('请输入双因素认证验证码')
      } else if (errorData?.require_captcha) {
        // 需要验证码 - 初始化极验
        setRequireCaptcha(true)
        setMood('idle')
        message.info('请完成验证码验证')
        initCaptcha(values)
        return // 不要在 finally 中 setLoading(false)，initCaptcha 会处理
      } else {
        setMood('error')
        message.error(errorData?.error || '操作失败')
        setTimeout(() => setMood('idle'), 2000)
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page" onMouseMove={handleMouseMove}>
      <div className="login-container" ref={containerRef}>
        {/* 左侧：卡通人物 */}
        <div className="login-left">
          <div className="characters-wrap">
            <Characters mouseX={mousePos.x} mouseY={mousePos.y} mood={mood} />
          </div>
        </div>

        {/* 右侧：表单 */}
        <div className="login-right">
          {checkingInit ? (
            <div style={{ textAlign: 'center', padding: '60px 0' }}>
              <div style={{ fontSize: 14, color: '#8c8c8c' }}>正在加载...</div>
            </div>
          ) : (
            <>
              <div className="login-header">
                {/* Logo */}
                <div className="login-logo">
                  <img src="/favicon.svg" alt="呆呆面板" width="48" height="48" style={{ borderRadius: 12 }} />
                </div>
                <h2>{isInit ? '初始化管理员' : '欢迎回来!'}</h2>
                <p>{isInit ? '首次使用，请设置管理员账号' : '请输入您的登录信息'}</p>
              </div>

              <Form
                form={form}
                size="large"
                onFinish={handleSubmit}
                autoComplete="off"
                initialValues={{ username: '', password: '' }}
              >
                <Form.Item
                  name="username"
                  rules={[
                    { required: true, message: '请输入用户名' },
                    { min: 2, message: '用户名至少 2 个字符' },
                  ]}
                >
                  <Input
                    prefix={<UserOutlined style={{ color: '#bfbfbf' }} />}
                    placeholder="用户名"
                    onFocus={handleUsernameFocus}
                    onBlur={handleBlur}
                  />
                </Form.Item>

                <Form.Item
                  name="password"
                  rules={[
                    { required: true, message: '请输入密码' },
                    ...(isInit ? [{ min: 8, message: '密码至少 8 个字符' }] : []),
                  ]}
                >
                  <Input
                    prefix={<LockOutlined style={{ color: '#bfbfbf' }} />}
                    placeholder={isInit ? '设置密码（至少 8 位）' : '密码'}
                    type={pwdVisible ? 'text' : 'password'}
                    onFocus={handlePasswordFocus}
                    onBlur={handleBlur}
                    suffix={
                      <span
                        onClick={togglePwdVisible}
                        style={{ cursor: 'pointer', color: '#8c8c8c', display: 'flex', alignItems: 'center' }}
                      >
                        {pwdVisible ? <EyeOutlined /> : <EyeInvisibleOutlined />}
                      </span>
                    }
                  />
                </Form.Item>

                {/* 2FA验证码输入框 */}
                {require2FA && (
                  <Form.Item
                    name="totp_token"
                    rules={[{ required: true, message: '请输入验证码' }]}
                  >
                    <Input
                      prefix={<SafetyOutlined style={{ color: '#bfbfbf' }} />}
                      placeholder="6位验证码或备用码"
                      maxLength={8}
                      onFocus={() => {
                        setFocusField('totp')
                        setMood('typing')
                      }}
                      onBlur={handleBlur}
                    />
                  </Form.Item>
                )}

                {/* 验证码提示 */}
                {requireCaptcha && (
                  <div style={{ marginBottom: 16, textAlign: 'center', color: '#8c8c8c', fontSize: 13 }}>
                    登录失败次数过多，需要完成验证码验证
                  </div>
                )}

                <Form.Item style={{ marginBottom: 12 }}>
                  <Button
                    type="primary"
                    htmlType="submit"
                    loading={loading}
                    block
                    className="login-btn"
                  >
                    {isInit ? '初始化并登录' : '登 录'}
                  </Button>
                </Form.Item>
              </Form>

              <div className="login-version">
                呆呆面板 v0.1.0
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
