import { useEffect, useState, useRef, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Card, Table, Button, Space, Input, Modal, Typography,
  message, Popconfirm, Upload, Timeline, Tag, Tooltip, Tree, Segmented, Row, Col,
} from 'antd'
import {
  PlusOutlined, UploadOutlined, ReloadOutlined,
  EditOutlined, DeleteOutlined, HistoryOutlined,
  RollbackOutlined, SaveOutlined, FileOutlined,
  SearchOutlined, ApartmentOutlined, UnorderedListOutlined,
  FolderOutlined, PlayCircleOutlined, StopOutlined,
  FullscreenOutlined, FullscreenExitOutlined, FormatPainterOutlined,
  FolderAddOutlined,
} from '@ant-design/icons'
import Editor from '@monaco-editor/react'
import { scriptApi } from '../../services/api'
import dayjs from 'dayjs'
import { useThemeStore } from '../../stores/themeStore'
import { useScriptDebugLogs } from '../../hooks/useScriptDebugLogs'
import { handleApiError, handleApiSuccess } from '../../utils/apiHelper'
import { formatUTCTime, formatTimestamp } from '../../utils/timeHelper'
import Ansi from 'ansi-to-react'

const { Title, Text } = Typography

const EXT_LANG_MAP: Record<string, string> = {
  '.py': 'python',
  '.js': 'javascript',
  '.ts': 'typescript',
  '.sh': 'shell',
  '.json': 'json',
  '.yaml': 'yaml',
  '.yml': 'yaml',
  '.md': 'markdown',
  '.html': 'html',
  '.htm': 'html',
  '.css': 'css',
  '.xml': 'xml',
  '.sql': 'sql',
  '.ini': 'ini',
  '.toml': 'ini',
  '.bat': 'bat',
  '.ps1': 'powershell',
}

const BINARY_EXTENSIONS = new Set(['.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.bmp', '.webp'])

interface ScriptFile {
  path: string
  name: string
  size: number
  mtime: number
}

interface VersionRecord {
  id: number
  script_path: string
  version: number
  message: string
  content_length: number
  created_at: string
}

export default function Scripts() {
  const navigate = useNavigate()
  const [files, setFiles] = useState<ScriptFile[]>([])
  const [loading, setLoading] = useState(false)
  const [searchKeyword, setSearchKeyword] = useState('')
  const [viewMode, setViewMode] = useState<'list' | 'tree'>('list')
  const [treeData, setTreeData] = useState<any[]>([])

  // 编辑器状态
  const [editorOpen, setEditorOpen] = useState(false)
  const [currentPath, setCurrentPath] = useState('')
  const [editorContent, setEditorContent] = useState('')
  const [saving, setSaving] = useState(false)
  const [isNew, setIsNew] = useState(false)
  const [fullscreen, setFullscreen] = useState(false)
  const [isBinary, setIsBinary] = useState(false)
  const [binaryDataUrl, setBinaryDataUrl] = useState('')

  // Monaco 编辑器引用
  const editorRef = useRef<any>(null)

  // 新建文件
  const [newModalOpen, setNewModalOpen] = useState(false)
  const [newFileName, setNewFileName] = useState('')

  // 新建文件夹
  const [newFolderModalOpen, setNewFolderModalOpen] = useState(false)
  const [newFolderPath, setNewFolderPath] = useState('')

  // 版本历史
  const [versionOpen, setVersionOpen] = useState(false)
  const [versions, setVersions] = useState<VersionRecord[]>([])
  const [versionPath, setVersionPath] = useState('')

  // 调试运行
  const [debugOpen, setDebugOpen] = useState(false)
  const [debugPath, setDebugPath] = useState('')
  const [debugRunId, setDebugRunId] = useState<string | null>(null)

  // 日志容器引用，用于自动滚动
  const logContainerRef = useRef<HTMLDivElement>(null)

  // 使用Hook获取调试日志
  const { logs: debugLogs, done: debugDone, status: debugStatus, exitCode: debugExitCode, error: debugError } = useScriptDebugLogs(debugRunId, debugOpen)

  const darkMode = useThemeStore((s) => s.darkMode)

  const filteredFiles = useMemo(() => {
    if (!searchKeyword.trim()) return files
    const kw = searchKeyword.toLowerCase()
    return files.filter(f => f.path.toLowerCase().includes(kw) || f.name.toLowerCase().includes(kw))
  }, [files, searchKeyword])

  const editorLanguage = useMemo(() => {
    const ext = currentPath.match(/\.[^.]+$/)?.[0] || ''
    return EXT_LANG_MAP[ext] || 'plaintext'
  }, [currentPath])

  useEffect(() => {
    fetchFiles()
    fetchTree()
  }, [])

  const fetchFiles = async () => {
    setLoading(true)
    try {
      const res = await scriptApi.list()
      setFiles(res.data.data || [])
    } catch (error) {
      handleApiError(error, '获取脚本列表失败')
    } finally {
      setLoading(false)
    }
  }

  const fetchTree = async () => {
    try {
      const res = await scriptApi.tree()
      setTreeData(res.data.data || [])
    } catch {
      // 静默
    }
  }

  const handleEdit = async (path: string) => {
    try {
      const res = await scriptApi.getContent(path)
      setCurrentPath(path)
      if (res.data.data.binary) {
        setIsBinary(true)
        setBinaryDataUrl(`data:${res.data.data.mime};base64,${res.data.data.content}`)
        setEditorContent('')
      } else {
        setIsBinary(false)
        setBinaryDataUrl('')
        setEditorContent(res.data.data.content)
      }
      setIsNew(false)
      setEditorOpen(true)
    } catch (error) {
      handleApiError(error, '读取文件内容失败')
    }
  }

  const handleSave = async () => {
    if (!currentPath) return
    setSaving(true)
    try {
      await scriptApi.saveContent({
        path: currentPath,
        content: editorContent,
      })
      handleApiSuccess('保存成功')
      if (isNew) {
        setEditorOpen(false)
        fetchFiles()
      }
    } catch (error) {
      handleApiError(error, '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleFormatCode = async () => {
    if (!editorRef.current) return

    const model = editorRef.current.getModel()
    if (!model) return

    const content = model.getValue()
    if (!content.trim()) {
      message.info('代码内容为空')
      return
    }

    try {
      let formatted = content

      // 根据语言选择格式化方式
      switch (editorLanguage) {
        case 'javascript':
        case 'typescript':
          // 使用 Prettier 格式化 JS/TS
          formatted = await formatWithPrettier(content, editorLanguage)
          break

        case 'python':
          // 使用后端 Black 格式化 Python
          formatted = await formatWithBackend(content, 'python', 'black')
          break

        case 'shell':
          // 使用后端 shfmt 格式化 Shell
          formatted = await formatWithBackend(content, 'shell')
          break

        case 'json':
          // JSON 格式化
          try {
            formatted = JSON.stringify(JSON.parse(content), null, 2)
          } catch {
            message.warning('JSON 格式错误，无法格式化')
            return
          }
          break

        default:
          // 尝试使用 Monaco 内置格式化
          const action = editorRef.current.getAction('editor.action.formatDocument')
          if (action) {
            await action.run()
            message.success('代码已格式化')
            return
          } else {
            // 基础格式化
            formatted = formatBasic(content)
          }
      }

      if (formatted !== content) {
        model.setValue(formatted)
        message.success('代码已格式化')
      } else {
        message.info('代码格式已正确')
      }
    } catch (error: any) {
      console.error('格式化失败:', error)
      message.error(error.message || '格式化失败')
    }
  }

  // 使用 Prettier 格式化
  const formatWithPrettier = async (code: string, language: string): Promise<string> => {
    try {
      const prettier = await import('prettier')

      const options: any = {
        semi: true,
        singleQuote: true,
        tabWidth: 2,
        trailingComma: 'es5',
        printWidth: 100,
      }

      if (language === 'javascript') {
        options.parser = 'babel'
      } else if (language === 'typescript') {
        options.parser = 'typescript'
      }

      return prettier.format(code, options)
    } catch (error: any) {
      throw new Error(`Prettier 格式化失败: ${error.message}`)
    }
  }

  // 使用后端 API 格式化
  const formatWithBackend = async (
    code: string,
    language: string,
    formatter?: string
  ): Promise<string> => {
    try {
      const res = await scriptApi.format({
        content: code,
        language,
        formatter,
      })
      return res.data.data.content
    } catch (error: any) {
      const errorMsg = error.response?.data?.error || error.message
      throw new Error(`后端格式化失败: ${errorMsg}`)
    }
  }

  // 基础格式化（通用）
  const formatBasic = (code: string): string => {
    const lines = code.split('\n')
    return lines.map(line => line.trimEnd()).join('\n')
  }

  const handleToggleFullscreen = () => {
    setFullscreen(!fullscreen)
  }

  const handleCreate = () => {
    setNewFileName('')
    setNewModalOpen(true)
  }

  const handleCreateFolder = () => {
    setNewFolderPath('')
    setNewFolderModalOpen(true)
  }

  const handleNewConfirm = () => {
    const name = newFileName.trim()
    if (!name) {
      message.warning('请输入文件名')
      return
    }
    if (!/\.[a-zA-Z0-9]+$/i.test(name)) {
      message.warning('文件名需包含扩展名')
      return
    }
    if (/\.\./.test(name)) {
      message.warning('文件名不能包含 ..')
      return
    }
    const ext = name.substring(name.lastIndexOf('.')).toLowerCase()
    if (BINARY_EXTENSIONS.has(ext)) {
      message.warning('二进制文件请使用上传功能')
      return
    }
    setNewModalOpen(false)
    setCurrentPath(name)
    setEditorContent('')
    setIsBinary(false)
    setBinaryDataUrl('')
    setIsNew(true)
    setEditorOpen(true)
  }

  const handleNewFolderConfirm = async () => {
    const path = newFolderPath.trim()
    if (!path) {
      message.warning('请输入文件夹路径')
      return
    }
    if (/\.\./.test(path)) {
      message.warning('路径不能包含 ..')
      return
    }
    if (!/^[\w\u4e00-\u9fff\-./]+$/.test(path)) {
      message.warning('路径包含非法字符')
      return
    }

    try {
      await scriptApi.createDirectory(path)
      handleApiSuccess('文件夹创建成功')
      setNewFolderModalOpen(false)
      fetchTree()
      fetchFiles()
    } catch (error) {
      handleApiError(error, '创建文件夹失败')
    }
  }

  const handleDelete = async (path: string) => {
    try {
      await scriptApi.delete(path)
      handleApiSuccess('删除成功')
      fetchFiles()
    } catch (error) {
      handleApiError(error, '删除失败')
    }
  }

  const handleUpload = async (file: File) => {
    try {
      await scriptApi.upload(file)
      handleApiSuccess('上传成功')
      fetchFiles()

      // 根据扩展名生成命令
      const fileName = file.name
      const ext = fileName.substring(fileName.lastIndexOf('.')).toLowerCase()
      const commandMap: Record<string, string> = {
        '.js': 'node',
        '.py': 'python',
        '.ts': 'ts-node',
        '.sh': 'bash',
      }
      const interpreter = commandMap[ext]
      if (interpreter) {
        Modal.confirm({
          title: '创建定时任务',
          content: `是否为脚本 "${fileName}" 创建定时任务？`,
          okText: '去创建',
          cancelText: '稍后再说',
          onOk: () => {
            const taskName = fileName.replace(/\.[^.]+$/, '')
            const command = `${interpreter} ${fileName}`
            navigate(`/tasks?autoCreate=1&script=${encodeURIComponent(fileName)}&name=${encodeURIComponent(taskName)}&command=${encodeURIComponent(command)}`)
          },
        })
      }
    } catch (error) {
      handleApiError(error, '上传失败')
    }
    return false
  }

  const handleShowVersions = async (path: string) => {
    setVersionPath(path)
    try {
      const res = await scriptApi.listVersions(path)
      setVersions(res.data.data || [])
      setVersionOpen(true)
    } catch (error) {
      handleApiError(error, '获取版本历史失败')
    }
  }

  const handleRollback = async (versionId: number) => {
    try {
      await scriptApi.rollback(versionId)
      handleApiSuccess('回滚成功')
      setVersionOpen(false)
      fetchFiles()
    } catch (error) {
      handleApiError(error, '回滚失败')
    }
  }

  const handleViewVersion = async (versionId: number) => {
    try {
      const res = await scriptApi.getVersion(versionId)
      const data = res.data.data
      setCurrentPath(data.script_path)
      setEditorContent(data.content)
      setIsNew(false)
      setVersionOpen(false)
      setEditorOpen(true)
    } catch (error) {
      handleApiError(error, '获取版本内容失败')
    }
  }

  // 调试运行相关函数
  const handleDebugRun = async (path: string) => {
    // 重置所有调试状态
    setDebugRunId(null)
    setDebugPath(path)
    setCurrentPath(path)

    // 先加载脚本内容
    try {
      const res = await scriptApi.getContent(path)
      setEditorContent(res.data.data.content)
    } catch (error) {
      handleApiError(error, '读取脚本内容失败')
      return
    }

    setDebugOpen(true)
  }

  const handleStartDebug = async () => {
    if (!debugPath) return

    try {
      const res = await scriptApi.run(debugPath)
      const runId = res.data.run_id
      setDebugRunId(runId)
    } catch (error) {
      handleApiError(error, '启动失败')
    }
  }

  const handleStopDebug = async () => {
    if (!debugRunId) return

    try {
      await scriptApi.stopRun(debugRunId)
      handleApiSuccess('已停止运行')
      // 不要立即清空 runId，让 Hook 继续获取最终状态
    } catch (error) {
      handleApiError(error, '停止失败')
    }
  }

  const handleCloseDebug = async () => {
    // 如果还在运行，先停止
    if (debugRunId && !debugDone) {
      try {
        await scriptApi.stopRun(debugRunId)
      } catch {
        // 忽略错误
      }
    }

    // 清理运行记录
    if (debugRunId) {
      try {
        await scriptApi.clearRun(debugRunId)
      } catch {
        // 忽略错误
      }
    }

    // 关闭弹窗并清理状态
    setDebugOpen(false)

    // 延迟清理 runId，让 Hook 有时间停止轮询
    setTimeout(() => {
      setDebugRunId(null)
    }, 100)
  }

  // 显示调试错误
  useEffect(() => {
    if (debugError) {
      message.error(debugError)
    }
  }, [debugError])

  // 日志更新时自动滚动到底部
  useEffect(() => {
    if (logContainerRef.current && debugLogs.length > 0) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight
    }
  }, [debugLogs])

  const columns = [
    {
      title: '文件名',
      dataIndex: 'path',
      key: 'path',
      render: (v: string) => (
        <Space>
          <FileOutlined style={{ color: '#1677FF' }} />
          <code style={{ fontSize: 13 }}>{v}</code>
        </Space>
      ),
    },
    {
      title: '大小',
      dataIndex: 'size',
      key: 'size',
      width: 100,
      render: (v: number) => {
        if (v < 1024) return `${v} B`
        return `${(v / 1024).toFixed(1)} KB`
      },
    },
    {
      title: '修改时间',
      dataIndex: 'mtime',
      key: 'mtime',
      width: 170,
      render: (v: number) => formatTimestamp(v),
    },
    {
      title: '操作',
      key: 'actions',
      width: 240,
      render: (_: any, record: ScriptFile) => (
        <Space size={4}>
          <Tooltip title="调试运行">
            <Button type="text" size="small" icon={<PlayCircleOutlined />} onClick={() => handleDebugRun(record.path)} />
          </Tooltip>
          <Tooltip title="编辑">
            <Button type="text" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record.path)} />
          </Tooltip>
          <Tooltip title="版本历史">
            <Button type="text" size="small" icon={<HistoryOutlined />} onClick={() => handleShowVersions(record.path)} />
          </Tooltip>
          <Popconfirm title="确定删除？" onConfirm={() => handleDelete(record.path)}>
            <Tooltip title="删除">
              <Button type="text" size="small" icon={<DeleteOutlined />} danger />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div className="animate-fade-in">
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <Title level={4} style={{ margin: 0, fontWeight: 600 }}>脚本管理</Title>
        <Space>
          <Input
            placeholder="搜索脚本"
            prefix={<SearchOutlined />}
            value={searchKeyword}
            onChange={(e) => setSearchKeyword(e.target.value)}
            allowClear
            style={{ width: 180 }}
          />
          <Segmented
            size="small"
            value={viewMode}
            onChange={(v) => setViewMode(v as 'list' | 'tree')}
            options={[
              { value: 'list', icon: <UnorderedListOutlined /> },
              { value: 'tree', icon: <ApartmentOutlined /> },
            ]}
          />
          <Button icon={<ReloadOutlined />} onClick={() => { fetchFiles(); fetchTree() }}>刷新</Button>
          <Upload
            showUploadList={false}
            beforeUpload={handleUpload}
          >
            <Button icon={<UploadOutlined />}>上传文件</Button>
          </Upload>
          <Button icon={<FolderAddOutlined />} onClick={handleCreateFolder}>新建文件夹</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>新建脚本</Button>
        </Space>
      </div>

      <Card style={{ borderRadius: 10 }} styles={{ body: { padding: viewMode === 'tree' ? 16 : 0 } }}>
        {viewMode === 'list' ? (
          <Table
            dataSource={filteredFiles}
            columns={columns}
            rowKey="path"
            loading={loading}
            size="middle"
            pagination={false}
            locale={{ emptyText: '暂无脚本文件' }}
          />
        ) : (
          <Tree
            showIcon
            defaultExpandAll
            treeData={treeData}
            icon={(props: any) => props.isLeaf ? <FileOutlined style={{ color: '#1677FF' }} /> : <FolderOutlined style={{ color: '#faad14' }} />}
            onSelect={(_, info) => {
              const node = info.node as any
              if (node.isLeaf) {
                handleEdit(node.key as string)
              }
            }}
            titleRender={(node: any) => (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                <span>{node.title}</span>
                {node.isLeaf && (
                  <Space size={0}>
                    <Tooltip title="调试运行">
                      <Button type="text" size="small" icon={<PlayCircleOutlined />} onClick={(e) => { e.stopPropagation(); handleDebugRun(node.key) }} />
                    </Tooltip>
                    <Tooltip title="编辑">
                      <Button type="text" size="small" icon={<EditOutlined />} onClick={(e) => { e.stopPropagation(); handleEdit(node.key) }} />
                    </Tooltip>
                    <Tooltip title="版本历史">
                      <Button type="text" size="small" icon={<HistoryOutlined />} onClick={(e) => { e.stopPropagation(); handleShowVersions(node.key) }} />
                    </Tooltip>
                    <Popconfirm title="确定删除？" onConfirm={() => handleDelete(node.key)}>
                      <Tooltip title="删除">
                        <Button type="text" size="small" icon={<DeleteOutlined />} danger onClick={(e) => e.stopPropagation()} />
                      </Tooltip>
                    </Popconfirm>
                  </Space>
                )}
              </span>
            )}
          />
        )}
      </Card>

      {/* 新建文件弹窗 */}
      <Modal
        title="新建脚本"
        open={newModalOpen}
        onOk={handleNewConfirm}
        onCancel={() => setNewModalOpen(false)}
        okText="创建"
      >
        <Input
          placeholder="文件名，如 checkin.py"
          value={newFileName}
          onChange={(e) => setNewFileName(e.target.value)}
          onPressEnter={handleNewConfirm}
          style={{ marginTop: 8 }}
        />
        <Text type="secondary" style={{ fontSize: 12, marginTop: 8, display: 'block' }}>
          支持 .py / .js / .sh / .ts / .txt / .json / .yaml / .md 等格式
        </Text>
      </Modal>

      {/* 新建文件夹弹窗 */}
      <Modal
        title="新建文件夹"
        open={newFolderModalOpen}
        onOk={handleNewFolderConfirm}
        onCancel={() => setNewFolderModalOpen(false)}
        okText="创建"
      >
        <Input
          placeholder="文件夹路径，如 utils 或 scripts/utils"
          value={newFolderPath}
          onChange={(e) => setNewFolderPath(e.target.value)}
          onPressEnter={handleNewFolderConfirm}
          style={{ marginTop: 8 }}
        />
        <Text type="secondary" style={{ fontSize: 12, marginTop: 8, display: 'block' }}>
          支持多级目录，如 scripts/utils/helpers
        </Text>
      </Modal>

      {/* 代码编辑器模态框 */}
      <Modal
        title={
          <Space>
            <span>{isNew ? '新建' : '编辑'}: {currentPath}</span>
          </Space>
        }
        open={editorOpen}
        onCancel={() => setEditorOpen(false)}
        width={fullscreen ? '100vw' : 1000}
        style={fullscreen ? { top: 0, maxWidth: '100vw', paddingBottom: 0 } : {}}
        styles={fullscreen ? { body: { height: 'calc(100vh - 110px)' } } : {}}
        footer={
          <Space>
            <Button icon={<FormatPainterOutlined />} onClick={handleFormatCode}>
              格式化
            </Button>
            <Button
              icon={fullscreen ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
              onClick={handleToggleFullscreen}
            >
              {fullscreen ? '退出全屏' : '全屏'}
            </Button>
            <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={handleSave}>
              保存
            </Button>
          </Space>
        }
      >
        <div style={{ height: fullscreen ? '100%' : '70vh', borderRadius: 8, overflow: 'hidden', border: '1px solid #d9d9d9' }}>
          {isBinary ? (
            <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: darkMode ? '#1e1e1e' : '#fafafa' }}>
              <img src={binaryDataUrl} alt={currentPath} style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }} />
            </div>
          ) : (
          <Editor
            height="100%"
            language={editorLanguage}
            theme={darkMode ? 'vs-dark' : 'light'}
            value={editorContent}
            onChange={(v) => setEditorContent(v || '')}
            onMount={(editor) => { editorRef.current = editor }}
            options={{
              fontSize: 14,
              minimap: { enabled: true },
              lineNumbers: 'on',
              scrollBeyondLastLine: false,
              wordWrap: 'on',
              tabSize: 2,
              automaticLayout: true,
              padding: { top: 12 },
              formatOnPaste: true,
              formatOnType: true,
            }}
          />
          )}
        </div>
      </Modal>

      {/* 版本历史模态框 */}
      <Modal
        title={`版本历史: ${versionPath}`}
        open={versionOpen}
        onCancel={() => setVersionOpen(false)}
        width={600}
        footer={null}
      >
        {versions.length === 0 ? (
          <Text type="secondary">暂无版本记录</Text>
        ) : (
          <Timeline
            items={versions.map((v) => ({
              children: (
                <div key={v.id} style={{ marginBottom: 8 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Space>
                      <Tag color="blue">v{v.version}</Tag>
                      <Text style={{ fontSize: 13 }}>{v.message}</Text>
                    </Space>
                    <Space size={4}>
                      <Button size="small" type="link" onClick={() => handleViewVersion(v.id)}>
                        查看
                      </Button>
                      <Popconfirm title="确定回滚到此版本？" onConfirm={() => handleRollback(v.id)}>
                        <Button size="small" type="link" icon={<RollbackOutlined />}>
                          回滚
                        </Button>
                      </Popconfirm>
                    </Space>
                  </div>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {formatUTCTime(v.created_at)} · {(v.content_length / 1024).toFixed(1)} KB
                  </Text>
                </div>
              ),
            }))}
          />
        )}
      </Modal>

      {/* 调试运行模态框 */}
      <Modal
        title={
          <Space>
            <PlayCircleOutlined />
            <span>调试运行: {debugPath}</span>
            {debugStatus === 'running' && <Tag color="processing">运行中</Tag>}
            {debugStatus === 'success' && <Tag color="success">执行成功</Tag>}
            {debugStatus === 'failed' && <Tag color="error">执行失败</Tag>}
            {debugStatus === 'stopped' && <Tag color="warning">已停止</Tag>}
            {debugExitCode !== null && debugDone && (
              <Text type="secondary" style={{ fontSize: 12 }}>
                (退出码: {debugExitCode})
              </Text>
            )}
          </Space>
        }
        open={debugOpen}
        onCancel={handleCloseDebug}
        width={1400}
        footer={
          <Space>
            {debugRunId && !debugDone ? (
              <Button danger icon={<StopOutlined />} onClick={handleStopDebug}>
                停止
              </Button>
            ) : null}
            {!debugRunId ? (
              <Button type="primary" icon={<PlayCircleOutlined />} onClick={handleStartDebug}>
                运行
              </Button>
            ) : null}
            <Button onClick={handleCloseDebug}>关闭</Button>
          </Space>
        }
      >
        <Row gutter={16} style={{ height: '70vh' }}>
          <Col span={12}>
            <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
              <div style={{ marginBottom: 8, fontWeight: 500 }}>脚本代码</div>
              <div style={{ flex: 1, borderRadius: 8, overflow: 'hidden', border: '1px solid #d9d9d9' }}>
                <Editor
                  height="100%"
                  language={editorLanguage}
                  theme={darkMode ? 'vs-dark' : 'light'}
                  value={editorContent}
                  options={{
                    fontSize: 14,
                    minimap: { enabled: false },
                    lineNumbers: 'on',
                    scrollBeyondLastLine: false,
                    wordWrap: 'on',
                    tabSize: 2,
                    automaticLayout: true,
                    padding: { top: 12 },
                    readOnly: true,
                  }}
                />
              </div>
            </div>
          </Col>
          <Col span={12}>
            <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
              <div style={{ marginBottom: 8, fontWeight: 500 }}>运行日志</div>
              <div
                ref={logContainerRef}
                style={{
                  flex: 1,
                  backgroundColor: darkMode ? '#1e1e1e' : '#f5f5f5',
                  borderRadius: 8,
                  padding: 16,
                  fontFamily: 'Consolas, Monaco, "Courier New", monospace',
                  fontSize: 13,
                  lineHeight: 1.6,
                  overflowY: 'auto',
                  overflowX: 'auto',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  border: `2px solid ${
                    debugStatus === 'success' ? '#52c41a' :
                    debugStatus === 'failed' ? '#ff4d4f' :
                    debugStatus === 'stopped' ? '#faad14' :
                    '#d9d9d9'
                  }`,
                  maxHeight: 'calc(70vh - 40px)',
                }}
              >
                {debugLogs.length === 0 ? (
                  <Text type="secondary">等待输出...</Text>
                ) : (
                  debugLogs.map((log, idx) => (
                    <div key={idx} style={{ color: darkMode ? '#d4d4d4' : '#333' }}>
                      <Ansi>{log}</Ansi>
                    </div>
                  ))
                )}
              </div>
            </div>
          </Col>
        </Row>
      </Modal>
    </div>
  )
}
