import { useState, useMemo, useCallback } from 'react'
import {
  Layout, Menu, Typography, Tag, Card, Table, Tabs,
  Input, Space, Tooltip, Button, theme, Drawer,
} from 'antd'
import {
  ApiOutlined, SearchOutlined, CopyOutlined,
  LockOutlined, UnlockOutlined, CheckOutlined,
  MenuOutlined,
} from '@ant-design/icons'
import {
  apiCategories, generateCodeExamples,
  type ApiEndpoint,
} from './apiData'
import './styles.css'

const { Sider, Content } = Layout
const { Title, Text } = Typography

export default function ApiDocs() {
  const [selectedId, setSelectedId] = useState(apiCategories[0].endpoints[0].id)
  const [searchText, setSearchText] = useState('')
  const [codeTab, setCodeTab] = useState('Shell')
  const [copiedKey, setCopiedKey] = useState('')
  const [contentKey, setContentKey] = useState(0)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const { token: themeToken } = theme.useToken()

  // 搜索过滤
  const filteredCategories = useMemo(() => {
    if (!searchText.trim()) return apiCategories
    const kw = searchText.toLowerCase()
    return apiCategories
      .map(cat => ({
        ...cat,
        endpoints: cat.endpoints.filter(
          ep => ep.title.toLowerCase().includes(kw) ||
            ep.path.toLowerCase().includes(kw) ||
            ep.method.toLowerCase().includes(kw)
        ),
      }))
      .filter(cat => cat.endpoints.length > 0)
  }, [searchText])

  const currentEndpoint = useMemo(() => {
    for (const cat of apiCategories) {
      for (const ep of cat.endpoints) {
        if (ep.id === selectedId) return ep
      }
    }
    return apiCategories[0].endpoints[0]
  }, [selectedId])

  const currentCategory = useMemo(() => {
    for (const cat of apiCategories) {
      if (cat.endpoints.some(ep => ep.id === selectedId)) return cat
    }
    return apiCategories[0]
  }, [selectedId])

  const codeExamples = useMemo(() => generateCodeExamples(currentEndpoint), [currentEndpoint])

  const handleCopy = useCallback((text: string, key: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedKey(key)
      setTimeout(() => setCopiedKey(''), 1500)
    })
  }, [])

  const handleSelect = useCallback((id: string) => {
    setSelectedId(id)
    setContentKey(k => k + 1)
    setMobileMenuOpen(false)
  }, [])

  // 统计接口总数
  const totalEndpoints = useMemo(() =>
    apiCategories.reduce((sum, cat) => sum + cat.endpoints.length, 0), [])

  // 侧边栏菜单
  const menuItems = filteredCategories.map(cat => ({
    key: cat.key,
    label: `${cat.label} (${cat.endpoints.length})`,
    type: 'group' as const,
    children: cat.endpoints.map(ep => ({
      key: ep.id,
      label: (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span className={`method-badge method-badge-sm method-${ep.method.toLowerCase()}`}>
            {ep.method}
          </span>
          <span style={{ fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {ep.title}
          </span>
        </div>
      ),
    })),
  }))

  // 参数表格列
  const paramColumns = [
    {
      title: '参数名',
      dataIndex: 'name',
      key: 'name',
      width: 150,
      render: (v: string) => (
        <Text code style={{ fontSize: 12, background: '#f5f5f5', padding: '2px 6px', borderRadius: 4 }}>{v}</Text>
      ),
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: 90,
      render: (v: string) => <Tag style={{ borderRadius: 4, fontSize: 11 }}>{v}</Tag>,
    },
    {
      title: '必填',
      dataIndex: 'required',
      key: 'required',
      width: 60,
      render: (v?: boolean) => v
        ? <Tag color="error" style={{ borderRadius: 10, fontSize: 11 }}>必填</Tag>
        : <Tag style={{ borderRadius: 10, fontSize: 11 }}>可选</Tag>,
    },
    {
      title: '说明',
      dataIndex: 'description',
      key: 'description',
      render: (v: string) => <span style={{ color: '#595959' }}>{v}</span>,
    },
    {
      title: '示例',
      dataIndex: 'example',
      key: 'example',
      width: 130,
      render: (v?: string) => v
        ? <Text type="secondary" style={{ fontFamily: 'monospace', fontSize: 12 }}>{v}</Text>
        : <Text type="secondary">-</Text>,
    },
  ]

  const renderParamTable = (label: string, params: any[] | undefined, index: number) => {
    if (!params || params.length === 0) return null
    return (
      <div className="param-section" style={{ animationDelay: `${index * 0.08}s` }}>
        <div className="param-section-header">{label}</div>
        <Table
          dataSource={params}
          columns={paramColumns}
          rowKey="name"
          pagination={false}
          size="small"
        />
      </div>
    )
  }

  const renderEndpoint = (ep: ApiEndpoint) => (
    <div key={contentKey} className="api-content-enter">
      {/* 面包屑 */}
      <div className="api-breadcrumb animate-fade-in">{currentCategory.label} / {ep.title}</div>

      {/* 标题 */}
      <h2 className="api-endpoint-title animate-fade-in delay-1">{ep.title}</h2>

      {/* URL 栏 */}
      <div className="url-bar animate-fade-in-up delay-2">
        <span className={`method-badge method-${ep.method.toLowerCase()}`}>{ep.method}</span>
        <span className="url-path">http://localhost:5000{ep.path}</span>
        <Tooltip title={copiedKey === 'url' ? '已复制' : '复制 URL'}>
          <Button
            type="text" size="small"
            icon={copiedKey === 'url' ? <CheckOutlined style={{ color: '#52c41a' }} /> : <CopyOutlined />}
            onClick={() => handleCopy(`http://localhost:5000${ep.path}`, 'url')}
          />
        </Tooltip>
      </div>

      {/* 描述 */}
      <p className="api-description animate-fade-in delay-2">{ep.description}</p>

      {/* 认证提示 */}
      <div className={`auth-banner ${ep.auth === 'jwt' ? 'auth-jwt' : 'auth-none'} animate-fade-in delay-3`}>
        {ep.auth === 'jwt' ? (
          <>
            <LockOutlined />
            <span>使用 JWT Token 鉴权，请在请求头中添加 <Text code style={{ fontSize: 12 }}>Authorization: Bearer {'<TOKEN>'}</Text></span>
          </>
        ) : (
          <>
            <UnlockOutlined />
            <span>此接口无需鉴权即可访问</span>
          </>
        )}
      </div>

      {/* 请求参数 */}
      {(ep.pathParams || ep.queryParams || ep.bodyParams) && (
        <Card
          size="small"
          className="card-hover animate-fade-in-up delay-3"
          style={{ borderRadius: 10, marginBottom: 20, overflow: 'hidden' }}
          styles={{ header: { background: '#fafafa', borderBottom: '1px solid #f0f0f0' }, body: { padding: 0 } }}
          title={<div className="section-title" style={{ marginBottom: 0, paddingLeft: 12 }}>请求参数</div>}
        >
          {renderParamTable('Path 参数', ep.pathParams, 0)}
          {renderParamTable('Query 参数', ep.queryParams, 1)}
          {renderParamTable('Body 参数（JSON）', ep.bodyParams, 2)}
        </Card>
      )}

      {/* 请求示例代码 */}
      <Card
        size="small"
        className="card-hover animate-fade-in-up delay-4"
        style={{ borderRadius: 10, marginBottom: 20 }}
        styles={{ header: { background: '#fafafa', borderBottom: '1px solid #f0f0f0' } }}
        title={<div className="section-title" style={{ marginBottom: 0, paddingLeft: 12 }}>请求示例代码</div>}
      >
        <Tabs
          activeKey={codeTab}
          onChange={setCodeTab}
          size="small"
          className="code-tabs"
          items={Object.keys(codeExamples).map(lang => ({
            key: lang,
            label: lang,
            children: (
              <div className="code-block-wrapper">
                <Tooltip title={copiedKey === `code-${lang}` ? '已复制' : '复制代码'}>
                  <Button
                    className="code-copy-btn"
                    type="primary"
                    ghost
                    size="small"
                    icon={copiedKey === `code-${lang}` ? <CheckOutlined /> : <CopyOutlined />}
                    onClick={() => handleCopy(codeExamples[lang], `code-${lang}`)}
                  />
                </Tooltip>
                <pre className="code-block">{codeExamples[lang]}</pre>
              </div>
            ),
          }))}
        />
      </Card>

      {/* 返回响应 */}
      {ep.responseExample && (
        <Card
          size="small"
          className="card-hover animate-fade-in-up delay-5"
          style={{ borderRadius: 10, marginBottom: 20 }}
          styles={{ header: { background: '#fafafa', borderBottom: '1px solid #f0f0f0' } }}
          title={<div className="section-title" style={{ marginBottom: 0, paddingLeft: 12 }}>返回响应</div>}
        >
          <div style={{ marginBottom: 16 }}>
            <span className="status-badge status-200">
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#52c41a', display: 'inline-block' }} />
              200 成功
            </span>
            <Text type="secondary" style={{ marginLeft: 12, fontSize: 13 }}>application/json</Text>
          </div>

          <div className="response-section">
            {/* 响应字段说明 */}
            {ep.responseFields && ep.responseFields.length > 0 && (
              <div className="response-fields">
                <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 8, color: '#595959' }}>Body 字段</Text>
                <Table
                  dataSource={ep.responseFields}
                  columns={[
                    {
                      title: '字段',
                      dataIndex: 'name',
                      key: 'name',
                      width: 140,
                      render: (v: string) => <Text code style={{ fontSize: 12 }}>{v}</Text>,
                    },
                    {
                      title: '类型',
                      dataIndex: 'type',
                      key: 'type',
                      width: 80,
                      render: (v: string) => <Tag style={{ borderRadius: 4, fontSize: 11 }}>{v}</Tag>,
                    },
                    {
                      title: '说明',
                      dataIndex: 'description',
                      key: 'description',
                    },
                  ]}
                  rowKey="name"
                  pagination={false}
                  size="small"
                />
              </div>
            )}

            {/* 响应示例 */}
            <div className="response-example">
              <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 8, color: '#595959' }}>响应示例</Text>
              <div className="code-block-wrapper">
                <Tooltip title={copiedKey === 'resp' ? '已复制' : '复制'}>
                  <Button
                    className="code-copy-btn"
                    type="primary"
                    ghost
                    size="small"
                    icon={copiedKey === 'resp' ? <CheckOutlined /> : <CopyOutlined />}
                    onClick={() => handleCopy(ep.responseExample!, 'resp')}
                  />
                </Tooltip>
                <pre className="code-block" style={{ maxHeight: 360 }}>{ep.responseExample}</pre>
              </div>
            </div>
          </div>
        </Card>
      )}
    </div>
  )

  const siderContent = (
    <>
      <div className="api-search">
        <Input
          placeholder="搜索接口..."
          prefix={<SearchOutlined style={{ color: '#bfbfbf' }} />}
          value={searchText}
          onChange={e => setSearchText(e.target.value)}
          allowClear
          style={{ borderRadius: 8 }}
        />
        <div style={{ padding: '8px 2px 0', fontSize: 12, color: '#8c8c8c' }}>
          共 {totalEndpoints} 个接口
        </div>
      </div>
      <Menu
        mode="inline"
        selectedKeys={[selectedId]}
        onClick={({ key }) => handleSelect(key)}
        items={menuItems}
        style={{ border: 'none', fontSize: 13 }}
      />
    </>
  )

  return (
    <div className="animate-fade-in">
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <Title level={4} style={{ margin: 0, fontWeight: 600 }}>
          <Space><ApiOutlined />开发接口文档</Space>
        </Title>
        <Button
          icon={<MenuOutlined />}
          className="api-mobile-menu-btn"
          style={{ display: 'none' }}
          onClick={() => setMobileMenuOpen(true)}
        >
          接口列表
        </Button>
      </div>

      {/* 移动端菜单抽屉 */}
      <Drawer
        title="接口列表"
        placement="left"
        open={mobileMenuOpen}
        onClose={() => setMobileMenuOpen(false)}
        width={280}
        styles={{ body: { padding: 0 } }}
      >
        {siderContent}
      </Drawer>

      <Layout style={{ background: 'transparent', minHeight: 'calc(100vh - 160px)' }}>
        {/* 左侧导航 */}
        <Sider
          width={280}
          className="api-sider"
          style={{
            marginRight: 16,
            overflow: 'auto',
            maxHeight: 'calc(100vh - 160px)',
            position: 'sticky',
            top: 80,
          }}
        >
          {siderContent}
        </Sider>

        {/* 右侧内容 */}
        <Content style={{
          background: themeToken.colorBgContainer,
          borderRadius: 10,
          padding: '28px 32px',
          overflow: 'auto',
        }}>
          {renderEndpoint(currentEndpoint)}
        </Content>
      </Layout>
    </div>
  )
}
