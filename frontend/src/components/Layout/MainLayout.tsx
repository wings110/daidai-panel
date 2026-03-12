import { useState, useEffect } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { Layout, Menu, Avatar, Dropdown, Typography, theme, Drawer, Space } from 'antd'
import {
  DashboardOutlined,
  ClockCircleOutlined,
  FileTextOutlined,
  CodeOutlined,
  KeyOutlined,
  ApiOutlined,
  CloudDownloadOutlined,
  BellOutlined,
  AppstoreOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  UserOutlined,
  LogoutOutlined,
  SettingOutlined,
  BookOutlined,
  SunOutlined,
  MoonOutlined,
} from '@ant-design/icons'
import { useAuthStore } from '../../stores/authStore'
import { useThemeStore } from '../../stores/themeStore'

const { Header, Sider, Content } = Layout
const { Text } = Typography

const MOBILE_BREAKPOINT = 768

const menuItems = [
  {
    key: '/dashboard',
    icon: <DashboardOutlined />,
    label: '仪表盘',
  },
  {
    key: '/tasks',
    icon: <ClockCircleOutlined />,
    label: '定时任务',
  },
  {
    key: '/scripts',
    icon: <CodeOutlined />,
    label: '脚本管理',
  },
  {
    key: '/envs',
    icon: <KeyOutlined />,
    label: '环境变量',
  },
  {
    key: '/logs',
    icon: <FileTextOutlined />,
    label: '执行日志',
  },
  {
    key: '/subscriptions',
    icon: <CloudDownloadOutlined />,
    label: '订阅管理',
  },
  {
    key: '/open-api',
    icon: <ApiOutlined />,
    label: '开放 API',
  },
  {
    key: '/notifications',
    icon: <BellOutlined />,
    label: '通知设置',
  },
  {
    key: '/deps',
    icon: <AppstoreOutlined />,
    label: '依赖管理',
  },
  {
    key: '/users',
    icon: <UserOutlined />,
    label: '用户管理',
  },
  {
    key: '/settings',
    icon: <SettingOutlined />,
    label: '系统设置',
  },
  {
    key: '/api-docs',
    icon: <BookOutlined />,
    label: '接口文档',
  },
]

function useIsMobile() {
  const [isMobile, setIsMobile] = useState(window.innerWidth < MOBILE_BREAKPOINT)
  useEffect(() => {
    const handler = () => setIsMobile(window.innerWidth < MOBILE_BREAKPOINT)
    window.addEventListener('resize', handler)
    return () => window.removeEventListener('resize', handler)
  }, [])
  return isMobile
}

export default function MainLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const { user, logout } = useAuthStore()
  const { darkMode, toggleDark } = useThemeStore()
  const { token } = theme.useToken()
  const isMobile = useIsMobile()

  const userMenuItems = [
    {
      key: 'settings',
      icon: <SettingOutlined />,
      label: '系统设置',
    },
    {
      type: 'divider' as const,
    },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      danger: true,
    },
  ]

  const handleUserMenu = ({ key }: { key: string }) => {
    if (key === 'logout') {
      logout()
    } else if (key === 'settings') {
      navigate('/settings')
    }
  }

  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(key)
    if (isMobile) setDrawerOpen(false)
  }

  const siderContent = (
    <>
      {/* Logo */}
      <div
        style={{
          height: 64,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderBottom: `1px solid ${token.colorBorderSecondary}`,
          gap: 8,
        }}
      >
        <img
          src="/favicon.svg"
          alt="呆呆面板"
          style={{
            width: 32,
            height: 32,
            borderRadius: 8,
          }}
        />
        {(!collapsed || isMobile) && (
          <Text strong style={{ fontSize: 16 }}>
            呆呆面板
          </Text>
        )}
      </div>

      {/* 导航菜单 */}
      <Menu
        mode="inline"
        selectedKeys={[location.pathname]}
        items={menuItems}
        onClick={handleMenuClick}
        style={{
          border: 'none',
          padding: '8px 0',
        }}
      />
    </>
  )

  return (
    <Layout style={{ minHeight: '100vh' }}>
      {/* 移动端：Drawer 侧边栏 */}
      {isMobile ? (
        <Drawer
          placement="left"
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          width={220}
          styles={{ body: { padding: 0 }, header: { display: 'none' } }}
        >
          {siderContent}
        </Drawer>
      ) : (
        /* 桌面端：固定侧边栏 */
        <Sider
          trigger={null}
          collapsible
          collapsed={collapsed}
          theme="light"
          style={{
            borderRight: `1px solid ${token.colorBorderSecondary}`,
            position: 'fixed',
            left: 0,
            top: 0,
            bottom: 0,
            zIndex: 100,
          }}
        >
          {siderContent}
        </Sider>
      )}

      {/* 主内容区 */}
      <Layout
        style={{
          marginLeft: isMobile ? 0 : (collapsed ? 80 : 200),
          transition: 'margin-left 0.2s',
        }}
      >
        {/* 顶栏 */}
        <Header
          style={{
            padding: isMobile ? '0 12px' : '0 24px',
            background: token.colorBgContainer,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: `1px solid ${token.colorBorderSecondary}`,
            position: 'sticky',
            top: 0,
            zIndex: 99,
            height: 64,
          }}
        >
          {/* 折叠/菜单按钮 */}
          <div
            onClick={() => isMobile ? setDrawerOpen(true) : setCollapsed(!collapsed)}
            style={{
              fontSize: 18,
              cursor: 'pointer',
              padding: '4px 8px',
              borderRadius: 6,
              color: token.colorTextSecondary,
              transition: 'all 0.2s',
            }}
          >
            {isMobile || collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
          </div>

          {/* 主题切换 + 用户信息 */}
          <Space size={8}>
          <div
            onClick={toggleDark}
            style={{
              fontSize: 18,
              cursor: 'pointer',
              padding: '4px 8px',
              borderRadius: 6,
              color: token.colorTextSecondary,
              transition: 'all 0.2s',
            }}
          >
            {darkMode ? <SunOutlined /> : <MoonOutlined />}
          </div>
          <Dropdown
            menu={{ items: userMenuItems, onClick: handleUserMenu }}
            placement="bottomRight"
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                cursor: 'pointer',
                padding: '4px 12px',
                borderRadius: 6,
                transition: 'background 0.2s',
              }}
            >
              <Avatar
                size={32}
                icon={<UserOutlined />}
                style={{ background: token.colorPrimary }}
              />
              {!isMobile && <Text>{user?.username || '管理员'}</Text>}
            </div>
          </Dropdown>
          </Space>
        </Header>

        {/* 内容区 */}
        <Content
          style={{
            margin: isMobile ? 12 : 24,
            minHeight: 'calc(100vh - 64px - 48px)',
          }}
        >
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
