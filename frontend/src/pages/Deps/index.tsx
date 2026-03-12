import { useEffect, useState } from 'react'
import {
  Card, Table, Button, Space, Input, Typography,
  message, Popconfirm, Tabs, Tag, Tooltip, Modal, Form,
} from 'antd'
import {
  PlusOutlined, ReloadOutlined, DeleteOutlined, SettingOutlined,
  AppstoreAddOutlined,
} from '@ant-design/icons'
import { depsApi, configApi } from '../../services/api'

const { Title, Text } = Typography

interface PkgRecord {
  name: string
  version: string
}

export default function Deps() {
  const [pythonPkgs, setPythonPkgs] = useState<PkgRecord[]>([])
  const [nodePkgs, setNodePkgs] = useState<PkgRecord[]>([])
  const [pyLoading, setPyLoading] = useState(false)
  const [nodeLoading, setNodeLoading] = useState(false)
  const [installName, setInstallName] = useState('')
  const [installing, setInstalling] = useState(false)
  const [activeTab, setActiveTab] = useState('python')
  const [registryModalOpen, setRegistryModalOpen] = useState(false)
  const [registryForm] = Form.useForm()
  const [registrySaving, setRegistrySaving] = useState(false)
  const [batchModalOpen, setBatchModalOpen] = useState(false)
  const [batchText, setBatchText] = useState('')
  const [batchInstalling, setBatchInstalling] = useState(false)
  const [searchKeyword, setSearchKeyword] = useState('')

  useEffect(() => {
    fetchPython()
    fetchNode()
  }, [])

  const fetchPython = async () => {
    setPyLoading(true)
    try {
      const res = await depsApi.listPython()
      setPythonPkgs(res.data.data || [])
    } catch {
      // 静默
    } finally {
      setPyLoading(false)
    }
  }

  const fetchNode = async () => {
    setNodeLoading(true)
    try {
      const res = await depsApi.listNode()
      setNodePkgs(res.data.data || [])
    } catch {
      // 静默
    } finally {
      setNodeLoading(false)
    }
  }

  const handleInstall = async () => {
    const name = installName.trim()
    if (!name) {
      message.warning('请输入包名')
      return
    }
    setInstalling(true)
    try {
      if (activeTab === 'python') {
        await depsApi.installPython(name)
        message.success(`Python 包 ${name} 安装成功`)
        fetchPython()
      } else {
        await depsApi.installNode(name)
        message.success(`Node 包 ${name} 安装成功`)
        fetchNode()
      }
      setInstallName('')
    } catch (err: any) {
      message.error(err?.response?.data?.error || '安装失败')
    } finally {
      setInstalling(false)
    }
  }

  const handleUninstallPython = async (name: string) => {
    try {
      await depsApi.uninstallPython(name)
      message.success(`${name} 已卸载`)
      fetchPython()
    } catch (err: any) {
      message.error(err?.response?.data?.error || '卸载失败')
    }
  }

  const handleUninstallNode = async (name: string) => {
    try {
      await depsApi.uninstallNode(name)
      message.success(`${name} 已卸载`)
      fetchNode()
    } catch (err: any) {
      message.error(err?.response?.data?.error || '卸载失败')
    }
  }

  const handleOpenRegistryModal = async () => {
    try {
      const res = await configApi.getAll()
      const configs = res.data.data || {}
      registryForm.setFieldsValue({
        python_registry: configs.python_registry?.value || '',
        node_registry: configs.node_registry?.value || '',
      })
      setRegistryModalOpen(true)
    } catch (err: any) {
      message.error('获取配置失败')
    }
  }

  const handleSaveRegistry = async () => {
    try {
      const values = await registryForm.validateFields()
      setRegistrySaving(true)
      await configApi.update({
        python_registry: values.python_registry || '',
        node_registry: values.node_registry || '',
      })
      message.success('镜像源配置已保存')
      setRegistryModalOpen(false)
    } catch (err: any) {
      if (err?.errorFields) return
      message.error(err?.response?.data?.error || '保存失败')
    } finally {
      setRegistrySaving(false)
    }
  }

  const handleBatchInstall = async () => {
    const text = batchText.trim()
    if (!text) {
      message.warning('请输入包名列表')
      return
    }

    const names = text.split('\n').map(line => line.trim()).filter(Boolean)
    if (names.length === 0) {
      message.warning('请输入有效的包名')
      return
    }

    setBatchInstalling(true)
    try {
      const res = await depsApi.batchInstallPython(names)
      const data = res.data

      if (data.results) {
        const successCount = data.results.filter((r: any) => r.success).length
        message.success(`批量安装完成，成功 ${successCount}/${names.length} 个`)

        const failures = data.results.filter((r: any) => !r.success)
        if (failures.length > 0) {
          Modal.warning({
            title: '部分包安装失败',
            content: (
              <div>
                {failures.map((f: any, idx: number) => (
                  <div key={idx} style={{ marginBottom: 4 }}>
                    {f.name}: {f.error}
                  </div>
                ))}
              </div>
            ),
          })
        }
      } else {
        message.success(data.message || '安装成功')
      }

      setBatchModalOpen(false)
      setBatchText('')
      fetchPython()
    } catch (err: any) {
      message.error(err?.response?.data?.error || '批量安装失败')
    } finally {
      setBatchInstalling(false)
    }
  }

  const filteredPythonPkgs = searchKeyword
    ? pythonPkgs.filter(pkg =>
        pkg.name.toLowerCase().includes(searchKeyword.toLowerCase())
      )
    : pythonPkgs

  const filteredNodePkgs = searchKeyword
    ? nodePkgs.filter(pkg =>
        pkg.name.toLowerCase().includes(searchKeyword.toLowerCase())
      )
    : nodePkgs

  const pyColumns = [
    {
      title: '包名',
      dataIndex: 'name',
      key: 'name',
      render: (v: string) => <code style={{ fontSize: 13 }}>{v}</code>,
    },
    {
      title: '版本',
      dataIndex: 'version',
      key: 'version',
      width: 120,
      render: (v: string) => <Tag>{v}</Tag>,
    },
    {
      title: '操作',
      key: 'actions',
      width: 80,
      render: (_: any, record: PkgRecord) => (
        <Popconfirm title={`确定卸载 ${record.name}？`} onConfirm={() => handleUninstallPython(record.name)}>
          <Tooltip title="卸载">
            <Button type="text" size="small" icon={<DeleteOutlined />} danger />
          </Tooltip>
        </Popconfirm>
      ),
    },
  ]

  const nodeColumns = [
    {
      title: '包名',
      dataIndex: 'name',
      key: 'name',
      render: (v: string) => <code style={{ fontSize: 13 }}>{v}</code>,
    },
    {
      title: '版本',
      dataIndex: 'version',
      key: 'version',
      width: 120,
      render: (v: string) => <Tag>{v}</Tag>,
    },
    {
      title: '操作',
      key: 'actions',
      width: 80,
      render: (_: any, record: PkgRecord) => (
        <Popconfirm title={`确定卸载 ${record.name}？`} onConfirm={() => handleUninstallNode(record.name)}>
          <Tooltip title="卸载">
            <Button type="text" size="small" icon={<DeleteOutlined />} danger />
          </Tooltip>
        </Popconfirm>
      ),
    },
  ]

  const tabItems = [
    {
      key: 'python',
      label: `Python (${pythonPkgs.length})`,
      children: (
        <Table
          dataSource={filteredPythonPkgs}
          columns={pyColumns}
          rowKey="name"
          loading={pyLoading}
          size="small"
          pagination={{ pageSize: 20, showTotal: (t: number) => `共 ${t} 个包` }}
          locale={{ emptyText: '暂无 Python 包' }}
        />
      ),
    },
    {
      key: 'node',
      label: `Node.js (${nodePkgs.length})`,
      children: (
        <Table
          dataSource={filteredNodePkgs}
          columns={nodeColumns}
          rowKey="name"
          loading={nodeLoading}
          size="small"
          pagination={{ pageSize: 20, showTotal: (t: number) => `共 ${t} 个包` }}
          locale={{ emptyText: '暂无 Node 包' }}
        />
      ),
    },
  ]

  return (
    <div className="animate-fade-in">
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <Title level={4} style={{ margin: 0, fontWeight: 600 }}>依赖管理</Title>
        <Space>
          <Input
            placeholder="搜索包名"
            value={searchKeyword}
            onChange={(e) => setSearchKeyword(e.target.value)}
            style={{ width: 180, borderRadius: 6 }}
            allowClear
          />
          <Input
            placeholder={`安装${activeTab === 'python' ? ' Python' : ' Node'} 包`}
            value={installName}
            onChange={(e) => setInstallName(e.target.value)}
            onPressEnter={handleInstall}
            style={{ width: 220, borderRadius: 6 }}
          />
          <Button
            type="primary"
            icon={<PlusOutlined />}
            loading={installing}
            onClick={handleInstall}
          >
            安装
          </Button>
          {activeTab === 'python' && (
            <Button
              icon={<AppstoreAddOutlined />}
              onClick={() => setBatchModalOpen(true)}
            >
              批量安装
            </Button>
          )}
          <Button icon={<SettingOutlined />} onClick={handleOpenRegistryModal}>
            镜像源设置
          </Button>
          <Button icon={<ReloadOutlined />} onClick={() => { fetchPython(); fetchNode() }}>
            刷新
          </Button>
        </Space>
      </div>

      <Card style={{ borderRadius: 10 }}>
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={tabItems}
        />
      </Card>

      <Modal
        title="软件包镜像源设置"
        open={registryModalOpen}
        onOk={handleSaveRegistry}
        onCancel={() => setRegistryModalOpen(false)}
        confirmLoading={registrySaving}
        width={600}
      >
        <Form
          form={registryForm}
          layout="vertical"
          style={{ marginTop: 20 }}
        >
          <Form.Item
            label="Python 包镜像源"
            name="python_registry"
            extra="例如: https://pypi.tuna.tsinghua.edu.cn/simple"
          >
            <Input placeholder="留空使用默认源" />
          </Form.Item>
          <Form.Item
            label="Node 包镜像源"
            name="node_registry"
            extra="例如: https://registry.npmmirror.com"
          >
            <Input placeholder="留空使用默认源" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 批量安装模态框 */}
      <Modal
        title="批量安装 Python 包"
        open={batchModalOpen}
        onOk={handleBatchInstall}
        onCancel={() => setBatchModalOpen(false)}
        confirmLoading={batchInstalling}
        width={600}
        okText="开始安装"
      >
        <div style={{ marginBottom: 12 }}>
          <Text type="secondary">每行一个包名，支持指定版本（如 requests==2.31.0）</Text>
        </div>
        <Input.TextArea
          value={batchText}
          onChange={(e) => setBatchText(e.target.value)}
          placeholder={`requests\nbeautifulsoup4\npandas==2.0.0`}
          rows={10}
          style={{ fontFamily: 'monospace' }}
        />
      </Modal>
    </div>
  )
}
