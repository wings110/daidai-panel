<script setup lang="ts">
import { ref, watch, nextTick, onBeforeUnmount, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { scriptApi } from '@/api/script'
import { ElMessage, ElMessageBox } from 'element-plus'
import MonacoEditor from '@/components/MonacoEditor.vue'

interface TreeNode {
  title: string
  key: string
  isLeaf: boolean
  children?: TreeNode[]
}

const router = useRouter()
const route = useRoute()

const fileTree = ref<TreeNode[]>([])
const selectedFile = ref('')
const fileContent = ref('')
const originalContent = ref('')
const isBinary = ref(false)
const loading = ref(false)
const saving = ref(false)
const treeLoading = ref(false)
const isEditing = ref(false)

const showCreateFileDialog = ref(false)
const showCreateDirDialog = ref(false)
const showRenameDialog = ref(false)
const showVersionDialog = ref(false)
const showDebugDialog = ref(false)
const debugCode = ref('')
const debugFileName = ref('')
const showUploadDialog = ref(false)
const uploadDir = ref('')
const uploadFileList = ref<File[]>([])
const showCodeRunner = ref(false)
const runnerCode = ref('')
const runnerLanguage = ref('python')
const runnerRunId = ref('')
const runnerLogs = ref<string[]>([])
const runnerRunning = ref(false)
const runnerExitCode = ref<number | null>(null)
let runnerTimer: ReturnType<typeof setInterval> | null = null

const newFileName = ref('')
const newFileParent = ref('')
const newDirName = ref('')
const newDirParent = ref('')
const renameTarget = ref('')
const renamePath = ref('')

const versions = ref<any[]>([])
const versionsLoading = ref(false)

const debugRunId = ref('')
const debugLogs = ref<string[]>([])
const debugRunning = ref(false)
const debugError = ref('')
const debugExitCode = ref<number | null>(null)
const debugCodeChanged = ref(false)
const formatting = ref(false)
let debugTimer: ReturnType<typeof setInterval> | null = null

const editorLanguage = computed(() => {
  if (!selectedFile.value) return 'javascript'
  const ext = selectedFile.value.split('.').pop()?.toLowerCase()
  const langMap: Record<string, string> = {
    js: 'javascript',
    ts: 'typescript',
    py: 'python',
    sh: 'shell',
    json: 'json',
    yaml: 'yaml',
    yml: 'yaml',
    md: 'markdown',
    html: 'html',
    css: 'css',
    xml: 'xml',
  }
  return langMap[ext || ''] || 'plaintext'
})

const hasChanges = ref(false)
watch(fileContent, (val) => {
  hasChanges.value = val !== originalContent.value
})

watch(showDebugDialog, (val) => {
  if (!val && debugTimer) {
    clearInterval(debugTimer)
    debugTimer = null
    debugRunning.value = false
  }
})

watch(showCodeRunner, (val) => {
  if (!val && runnerTimer) {
    clearInterval(runnerTimer)
    runnerTimer = null
    runnerRunning.value = false
  }
})

const allFolders = computed(() => {
  const folders: string[] = ['']
  const collectFolders = (nodes: TreeNode[], prefix = '') => {
    for (const node of nodes) {
      if (!node.isLeaf) {
        const path = prefix ? `${prefix}/${node.title}` : node.title
        folders.push(path)
        if (node.children) {
          collectFolders(node.children, path)
        }
      }
    }
  }
  collectFolders(fileTree.value)
  return folders
})

async function loadTree() {
  treeLoading.value = true
  try {
    const res = await scriptApi.tree()
    fileTree.value = res.data || []
  } catch {
    ElMessage.error('加载文件树失败')
  } finally {
    treeLoading.value = false
  }
}
loadTree()

function handleKeyDown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key === 's') {
    e.preventDefault()
    if (selectedFile.value && !isBinary.value && hasChanges.value) {
      handleSave()
    }
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeyDown)
  const fileParam = route.query.file as string
  if (fileParam) {
    selectedFile.value = fileParam
    loadFileContent(fileParam)
    router.replace({ path: '/scripts' })
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleKeyDown)
  if (debugTimer) {
    clearInterval(debugTimer)
    debugTimer = null
  }
  if (runnerTimer) {
    clearInterval(runnerTimer)
    runnerTimer = null
  }
})

async function handleNodeClick(data: TreeNode) {
  if (!data.isLeaf) return
  if (hasChanges.value) {
    try {
      await ElMessageBox.confirm('当前文件有未保存的修改，是否放弃？', '提示', {
        confirmButtonText: '放弃',
        cancelButtonText: '取消',
        type: 'warning'
      })
    } catch {
      return
    }
  }
  selectedFile.value = data.key
  isEditing.value = false
  await loadFileContent(data.key)
}

async function loadFileContent(path: string) {
  loading.value = true
  try {
    const res = await scriptApi.getContent(path)
    isBinary.value = res.data.is_binary
    fileContent.value = res.data.content
    originalContent.value = res.data.content
    hasChanges.value = false
  } catch {
    ElMessage.error('加载文件内容失败')
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  if (!selectedFile.value || isBinary.value) return
  saving.value = true
  try {
    let versionMessage = 'V1 初始版本'
    if (originalContent.value !== '') {
      try {
        const res = await scriptApi.listVersions(selectedFile.value)
        const versionCount = res.data?.length || 0
        versionMessage = `V${versionCount + 1} 更新`
      } catch {
        versionMessage = 'V2 更新'
      }
    }
    await scriptApi.saveContent(selectedFile.value, fileContent.value, versionMessage)
    originalContent.value = fileContent.value
    hasChanges.value = false
    ElMessage.success('保存成功')
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function handleCreateFile() {
  if (!newFileName.value.trim()) return
  try {
    const fullPath = newFileParent.value
      ? `${newFileParent.value}/${newFileName.value.trim()}`
      : newFileName.value.trim()
    await scriptApi.saveContent(fullPath, '', 'V1 初始版本')
    ElMessage.success('创建成功')
    showCreateFileDialog.value = false
    newFileName.value = ''
    newFileParent.value = ''
    await loadTree()
    selectedFile.value = fullPath
    isEditing.value = true
    await loadFileContent(fullPath)
  } catch {
    ElMessage.error('创建失败')
  }
}

async function handleCreateDir() {
  if (!newDirName.value.trim()) return
  try {
    const fullPath = newDirParent.value
      ? `${newDirParent.value}/${newDirName.value.trim()}`
      : newDirName.value.trim()
    await scriptApi.createDirectory(fullPath)
    ElMessage.success('创建成功')
    showCreateDirDialog.value = false
    newDirName.value = ''
    newDirParent.value = ''
    await loadTree()
  } catch {
    ElMessage.error('创建失败')
  }
}

async function handleDelete(path: string) {
  try {
    await ElMessageBox.confirm(`确定要删除 ${path} 吗？`, '确认删除', { type: 'warning' })
    await scriptApi.delete(path)
    ElMessage.success('删除成功')
    if (selectedFile.value === path) {
      selectedFile.value = ''
      fileContent.value = ''
      originalContent.value = ''
    }
    await loadTree()
  } catch { /* cancelled */ }
}

function allowDrag(draggingNode: any) {
  return draggingNode.data.isLeaf
}

function allowDrop(draggingNode: any, dropNode: any, type: string) {
  if (type === 'inner') {
    return !dropNode.data.isLeaf
  }
  return false
}

async function handleNodeDrop(draggingNode: any, dropNode: any) {
  const sourcePath = draggingNode.data.key
  const targetDir = dropNode.data.key
  try {
    await scriptApi.move(sourcePath, targetDir)
    ElMessage.success('移动成功')
    if (selectedFile.value === sourcePath) {
      const fileName = sourcePath.split('/').pop() || sourcePath
      selectedFile.value = targetDir ? `${targetDir}/${fileName}` : fileName
    }
    await loadTree()
  } catch {
    ElMessage.error('移动失败')
    await loadTree()
  }
}

async function handleRename() {
  if (!renameTarget.value.trim()) return
  try {
    const res = await scriptApi.rename(renamePath.value, renameTarget.value.trim())
    ElMessage.success('重命名成功')
    showRenameDialog.value = false
    if (selectedFile.value === renamePath.value) {
      selectedFile.value = res.new_path || renameTarget.value.trim()
    }
    await loadTree()
  } catch {
    ElMessage.error('重命名失败')
  }
}

function openRename(path: string) {
  renamePath.value = path
  renameTarget.value = path.split('/').pop() || path
  showRenameDialog.value = true
}

async function handleUpload(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  if (uploadDir.value) {
    formData.append('dir', uploadDir.value)
  }
  try {
    await scriptApi.upload(formData)
    ElMessage.success('上传成功')
    showUploadDialog.value = false
    await loadTree()

    const targetPath = uploadDir.value ? `${uploadDir.value}/${file.name}` : file.name
    try {
      await ElMessageBox.confirm('是否将此脚本添加到定时任务？', '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'info'
      })
      navigateToTaskWithScript(targetPath)
    } catch {}
  } catch {
    ElMessage.error('上传失败')
  }
  return false
}

function handleUploadFileChange(file: any) {
  uploadFileList.value = [file.raw]
}

async function handleUploadSubmit() {
  if (uploadFileList.value.length === 0) {
    ElMessage.warning('请选择文件')
    return
  }
  const file = uploadFileList.value[0]
  if (!file) return
  await handleUpload(file)
}

function navigateToTaskWithScript(filePath: string) {
  const fileName = filePath.split('/').pop() || filePath
  const taskName = fileName.replace(/\.[^/.]+$/, '')
  const command = `task ${filePath}`
  router.push({
    path: '/tasks',
    query: { autoCreate: '1', name: taskName, command }
  })
}

function handleAddToTask() {
  if (!selectedFile.value) return
  navigateToTaskWithScript(selectedFile.value)
}

async function loadVersions() {
  if (!selectedFile.value) return
  versionsLoading.value = true
  showVersionDialog.value = true
  try {
    const res = await scriptApi.listVersions(selectedFile.value)
    versions.value = res.data || []
  } catch {
    ElMessage.error('加载版本历史失败')
  } finally {
    versionsLoading.value = false
  }
}

async function handleRollback(versionId: number) {
  try {
    await ElMessageBox.confirm('确定要回滚到此版本吗？', '确认回滚', { type: 'warning' })
    await scriptApi.rollback(versionId)
    ElMessage.success('回滚成功')
    showVersionDialog.value = false
    await loadFileContent(selectedFile.value)
  } catch { /* cancelled */ }
}

async function handleDebugRun() {
  if (!selectedFile.value) return
  debugCode.value = fileContent.value
  debugFileName.value = getFileName(selectedFile.value)
  debugLogs.value = []
  debugRunning.value = false
  debugError.value = ''
  debugExitCode.value = null
  debugRunId.value = ''
  debugCodeChanged.value = false
  showDebugDialog.value = true
}

async function handleDebugStart() {
  if (!selectedFile.value) return
  if (debugCodeChanged.value) {
    try {
      await scriptApi.saveContent(selectedFile.value, debugCode.value)
      fileContent.value = debugCode.value
      debugCodeChanged.value = false
    } catch {
      ElMessage.error('保存代码失败')
      return
    }
  }
  debugLogs.value = []
  debugError.value = ''
  debugExitCode.value = null
  debugRunning.value = true
  try {
    const res = await scriptApi.debugRun({ path: selectedFile.value })
    debugRunId.value = res.run_id
    pollDebugLogs()
  } catch (err: any) {
    debugError.value = err?.response?.data?.error || err?.message || '调试运行失败'
    ElMessage.error(debugError.value)
    debugRunning.value = false
  }
}

function pollDebugLogs() {
  if (debugTimer) clearInterval(debugTimer)
  debugTimer = setInterval(async () => {
    if (!debugRunId.value) {
      if (debugTimer) {
        clearInterval(debugTimer)
        debugTimer = null
      }
      return
    }
    try {
      const res = await scriptApi.debugLogs(debugRunId.value)
      debugLogs.value = res.data.logs || []
      if (res.data.done) {
        debugRunning.value = false
        if (debugTimer) {
          clearInterval(debugTimer)
          debugTimer = null
        }
        if (res.data.status === 'failed') {
          debugExitCode.value = res.data.exit_code ?? null
          debugError.value = 'failed'
        }
      }
    } catch {
      debugRunning.value = false
      if (debugTimer) {
        clearInterval(debugTimer)
        debugTimer = null
      }
    }
  }, 500)
}

async function handleDebugStop() {
  if (!debugRunId.value) return
  try {
    await scriptApi.debugStop(debugRunId.value)
  } catch { /* ignore */ }
  debugRunning.value = false
  if (debugTimer) {
    clearInterval(debugTimer)
    debugTimer = null
  }
  try {
    const res = await scriptApi.debugLogs(debugRunId.value)
    debugLogs.value = res.data.logs || []
  } catch { /* ignore */ }
}

async function handleFormat() {
  if (!selectedFile.value || isBinary.value) return
  const langMap: Record<string, string> = {
    py: 'python', sh: 'shell', json: 'json',
  }
  const ext = selectedFile.value.split('.').pop()?.toLowerCase() || ''
  const lang = langMap[ext]
  if (!lang) {
    ElMessage.warning('该文件类型不支持格式化')
    return
  }
  formatting.value = true
  try {
    const res = await scriptApi.format({ content: fileContent.value, language: lang })
    if (res.data?.content) {
      fileContent.value = res.data.content
      ElMessage.success('格式化完成')
    }
  } catch {
    ElMessage.error('格式化失败')
  } finally {
    formatting.value = false
  }
}

function handleDownload() {
  if (!selectedFile.value) return
  const blob = new Blob([fileContent.value], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = getFileName(selectedFile.value)
  a.click()
  URL.revokeObjectURL(url)
}

function openCodeRunner() {
  runnerCode.value = ''
  runnerLanguage.value = 'python'
  runnerLogs.value = []
  runnerRunning.value = false
  runnerExitCode.value = null
  runnerRunId.value = ''
  showCodeRunner.value = true
}

async function handleRunCode() {
  if (!runnerCode.value.trim()) {
    ElMessage.warning('请输入代码')
    return
  }
  runnerLogs.value = []
  runnerExitCode.value = null
  runnerRunning.value = true
  try {
    const res = await scriptApi.runCode(runnerCode.value, runnerLanguage.value)
    runnerRunId.value = res.run_id
    pollRunnerLogs()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.error || '运行失败')
    runnerRunning.value = false
  }
}

function pollRunnerLogs() {
  if (runnerTimer) clearInterval(runnerTimer)
  runnerTimer = setInterval(async () => {
    if (!runnerRunId.value) {
      if (runnerTimer) { clearInterval(runnerTimer); runnerTimer = null }
      return
    }
    try {
      const res = await scriptApi.debugLogs(runnerRunId.value)
      runnerLogs.value = res.data.logs || []
      if (res.data.done) {
        runnerRunning.value = false
        runnerExitCode.value = res.data.exit_code ?? null
        if (runnerTimer) { clearInterval(runnerTimer); runnerTimer = null }
      }
    } catch {
      runnerRunning.value = false
      if (runnerTimer) { clearInterval(runnerTimer); runnerTimer = null }
    }
  }, 500)
}

async function handleStopRunner() {
  if (!runnerRunId.value) return
  try { await scriptApi.debugStop(runnerRunId.value) } catch {}
  runnerRunning.value = false
  if (runnerTimer) { clearInterval(runnerTimer); runnerTimer = null }
}

function getFileIcon(node: TreeNode) {
  if (!node.isLeaf) return 'Folder'
  return 'Document'
}

function getFileIconColor(node: TreeNode): string {
  if (!node.isLeaf) return '#e6a23c'
  const ext = node.title.split('.').pop()?.toLowerCase()
  switch (ext) {
    case 'js': return '#f0db4f'
    case 'ts': return '#3178c6'
    case 'py': return '#4b8bbe'
    case 'sh': return '#4eaa25'
    case 'json': return '#e37e36'
    case 'yaml': case 'yml': return '#cb171e'
    case 'md': return '#083fa1'
    case 'html': return '#e34c26'
    case 'css': return '#264de4'
    default: return 'var(--el-text-color-secondary)'
  }
}

function getFileName(path: string) {
  return path.split('/').pop() || path
}
</script>

<template>
  <div class="scripts-page">
    <div class="scripts-sidebar">
      <div class="sidebar-header">
        <span class="sidebar-title">脚本文件</span>
        <div class="sidebar-actions">
          <el-tooltip content="新建文件" placement="bottom">
            <el-button class="action-btn" circle @click="showCreateFileDialog = true">
              <el-icon :size="14"><DocumentAdd /></el-icon>
            </el-button>
          </el-tooltip>
          <el-tooltip content="新建目录" placement="bottom">
            <el-button class="action-btn" circle @click="showCreateDirDialog = true">
              <el-icon :size="14"><FolderAdd /></el-icon>
            </el-button>
          </el-tooltip>
          <el-tooltip content="上传文件" placement="bottom">
            <el-button class="action-btn" circle @click="showUploadDialog = true; uploadDir = ''; uploadFileList = []">
              <el-icon :size="14"><Upload /></el-icon>
            </el-button>
          </el-tooltip>
          <el-tooltip content="代码运行器" placement="bottom">
            <el-button class="action-btn" circle @click="openCodeRunner">
              <el-icon :size="14"><VideoPlay /></el-icon>
            </el-button>
          </el-tooltip>
          <el-tooltip content="刷新" placement="bottom">
            <el-button class="action-btn" circle @click="loadTree">
              <el-icon :size="14"><Refresh /></el-icon>
            </el-button>
          </el-tooltip>
        </div>
      </div>
      <div class="sidebar-tree" v-loading="treeLoading">
        <el-tree
          :data="fileTree"
          node-key="key"
          :props="{ children: 'children', label: 'title' }"
          :highlight-current="true"
          :expand-on-click-node="true"
          draggable
          :allow-drag="allowDrag"
          :allow-drop="allowDrop"
          @node-drop="handleNodeDrop"
          @node-click="handleNodeClick"
        >
          <template #default="{ data }">
            <div class="tree-node">
              <el-icon size="14" :style="{ color: getFileIconColor(data) }">
                <component :is="getFileIcon(data)" />
              </el-icon>
              <span class="tree-node-label">{{ data.title }}</span>
              <span v-if="data.isLeaf && data.title.includes('.')" class="file-ext-badge">{{ data.title.split('.').pop()?.toUpperCase() }}</span>
              <div class="tree-node-actions" @click.stop>
                <el-dropdown trigger="click" size="small">
                  <el-icon class="more-btn" :size="18"><MoreFilled /></el-icon>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item @click="openRename(data.key)">重命名</el-dropdown-item>
                      <el-dropdown-item @click="handleDelete(data.key)">删除</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </div>
            </div>
          </template>
        </el-tree>
      </div>
    </div>

    <div class="scripts-editor">
      <div v-if="!selectedFile" class="editor-placeholder">
        <el-empty description="选择一个文件查看内容" />
      </div>
      <template v-else>
        <div class="editor-header">
          <div class="editor-file-info">
            <el-icon><Document /></el-icon>
            <span>{{ getFileName(selectedFile) }}</span>
            <el-tag v-if="hasChanges" size="small" type="warning">未保存</el-tag>
          </div>
          <div class="editor-actions">
            <el-button v-if="!isEditing" size="default" type="primary" @click="isEditing = true" :disabled="isBinary">
              <el-icon><Edit /></el-icon>编辑
            </el-button>
            <el-button v-if="isEditing" size="default" type="success" @click="handleDebugRun" :disabled="isBinary">
              <el-icon><VideoPlay /></el-icon>调试
            </el-button>
            <el-button size="default" type="primary" @click="handleAddToTask" :disabled="isBinary">
              <el-icon><Plus /></el-icon>添加任务
            </el-button>
            <el-button v-if="isEditing" size="default" type="primary" @click="handleSave" :loading="saving" :disabled="!hasChanges || isBinary">
              <el-icon><Check /></el-icon>保存
            </el-button>
            <el-button v-if="isEditing" size="default" @click="handleFormat" :loading="formatting" :disabled="isBinary">
              <el-icon><MagicStick /></el-icon>格式化
            </el-button>
            <el-dropdown trigger="click">
              <el-button size="default">
                <el-icon><MoreFilled /></el-icon>更多
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="loadVersions" :disabled="isBinary">
                    <el-icon><Clock /></el-icon>版本历史
                  </el-dropdown-item>
                  <el-dropdown-item @click="openRename(selectedFile)">
                    <el-icon><Edit /></el-icon>重命名
                  </el-dropdown-item>
                  <el-dropdown-item @click="handleDownload" :disabled="isBinary">
                    <el-icon><Download /></el-icon>下载
                  </el-dropdown-item>
                  <el-dropdown-item divided @click="handleDelete(selectedFile)">
                    <el-icon><Delete /></el-icon>删除
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>
        <div class="editor-content" v-loading="loading">
          <div v-if="isBinary" class="binary-notice">
            <el-result icon="info" title="二进制文件" sub-title="该文件为二进制格式，无法在线编辑" />
          </div>
          <MonacoEditor
            v-else
            v-model="fileContent"
            :language="editorLanguage"
            :readonly="!isEditing"
            class="code-editor"
          />
        </div>
      </template>
    </div>

    <el-dialog v-model="showCreateFileDialog" title="新建文件" width="480px">
      <el-form label-width="80px">
        <el-form-item label="上级目录">
          <el-select v-model="newFileParent" placeholder="根目录" clearable style="width: 100%">
            <el-option label="根目录" value="" />
            <el-option v-for="folder in allFolders.filter(f => f)" :key="folder" :label="folder" :value="folder" />
          </el-select>
        </el-form-item>
        <el-form-item label="文件名">
          <el-input v-model="newFileName" placeholder="如: script.py" @keyup.enter="handleCreateFile" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateFileDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCreateFile">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showCreateDirDialog" title="新建目录" width="480px">
      <el-form label-width="80px">
        <el-form-item label="上级目录">
          <el-select v-model="newDirParent" placeholder="根目录" clearable style="width: 100%">
            <el-option label="根目录" value="" />
            <el-option v-for="folder in allFolders.filter(f => f)" :key="folder" :label="folder" :value="folder" />
          </el-select>
        </el-form-item>
        <el-form-item label="目录名">
          <el-input v-model="newDirName" placeholder="如: utils" @keyup.enter="handleCreateDir" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDirDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCreateDir">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showRenameDialog" title="重命名" width="400px">
      <el-input v-model="renameTarget" placeholder="新名称" @keyup.enter="handleRename" />
      <template #footer>
        <el-button @click="showRenameDialog = false">取消</el-button>
        <el-button type="primary" @click="handleRename">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showVersionDialog" title="版本历史" width="600px">
      <el-table :data="versions" v-loading="versionsLoading" max-height="400px">
        <el-table-column prop="version" label="版本" width="80" />
        <el-table-column prop="message" label="备注" />
        <el-table-column prop="content_length" label="大小" width="100">
          <template #default="{ row }">{{ (row.content_length / 1024).toFixed(1) }} KB</template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" width="180">
          <template #default="{ row }">{{ new Date(row.created_at).toLocaleString() }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="handleRollback(row.id)">回滚</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <el-dialog v-model="showUploadDialog" title="上传文件" width="480px">
      <el-form label-width="80px">
        <el-form-item label="目标目录">
          <el-select v-model="uploadDir" placeholder="根目录" clearable style="width: 100%">
            <el-option label="根目录" value="" />
            <el-option v-for="folder in allFolders.filter(f => f)" :key="folder" :label="folder" :value="folder" />
          </el-select>
        </el-form-item>
        <el-form-item label="选择文件">
          <el-upload
            :auto-upload="false"
            :show-file-list="true"
            :limit="1"
            :on-change="handleUploadFileChange"
            drag
          >
            <el-icon :size="40"><Upload /></el-icon>
            <div>拖拽文件到此处或点击选择</div>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showUploadDialog = false">取消</el-button>
        <el-button type="primary" @click="handleUploadSubmit">上传</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showCodeRunner" title="代码运行器" width="90%" :close-on-click-modal="false" top="5vh">
      <div class="debug-container">
        <div class="debug-code-panel">
          <div class="panel-header">
            <el-icon><Edit /></el-icon>
            <span>代码编辑</span>
            <el-select v-model="runnerLanguage" size="small" style="width: 130px; margin-left: auto">
              <el-option label="Python" value="python" />
              <el-option label="JavaScript" value="javascript" />
              <el-option label="TypeScript" value="typescript" />
              <el-option label="Shell" value="shell" />
            </el-select>
          </div>
          <div class="panel-content" style="padding: 0">
            <MonacoEditor
              v-model="runnerCode"
              :language="runnerLanguage === 'shell' ? 'shell' : runnerLanguage"
              style="height: 100%; min-height: 400px"
            />
          </div>
        </div>
        <div class="debug-log-panel">
          <div class="panel-header">
            <el-icon><Tickets /></el-icon>
            <span>运行输出</span>
            <el-tag v-if="runnerRunning" type="warning" size="small" effect="plain">运行中</el-tag>
            <el-tag v-else-if="runnerLogs.length > 0" :type="runnerExitCode === 0 ? 'success' : 'danger'" size="small" effect="plain">
              {{ runnerExitCode === 0 ? '成功' : '失败' }}
            </el-tag>
          </div>
          <div class="panel-content">
            <pre v-if="runnerLogs.length > 0" class="debug-logs">{{ runnerLogs.join('\n') }}</pre>
            <el-empty v-else description="点击运行按钮执行代码" :image-size="80" />
          </div>
        </div>
      </div>
      <template #footer>
        <el-button v-if="!runnerRunning" type="primary" @click="handleRunCode">
          <el-icon><VideoPlay /></el-icon>运行
        </el-button>
        <el-button v-if="runnerRunning" type="danger" @click="handleStopRunner">
          <el-icon><VideoPause /></el-icon>停止
        </el-button>
        <el-button @click="showCodeRunner = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showDebugDialog" title="调试运行" width="90%" :close-on-click-modal="false" top="5vh">
      <div class="debug-container">
        <div class="debug-code-panel">
          <div class="panel-header">
            <el-icon><Edit /></el-icon>
            <span>{{ debugFileName }}</span>
            <el-tag v-if="debugCodeChanged" type="warning" size="small" effect="plain">已修改</el-tag>
          </div>
          <div class="panel-content" style="padding: 0">
            <MonacoEditor
              v-model="debugCode"
              :language="editorLanguage"
              style="height: 100%; min-height: 400px"
              @update:modelValue="debugCodeChanged = true"
            />
          </div>
        </div>
        <div class="debug-log-panel">
          <div class="panel-header">
            <el-icon><Tickets /></el-icon>
            <span>调试日志</span>
            <el-tag v-if="debugRunning" type="warning" size="small" effect="plain">运行中</el-tag>
            <el-tag v-else-if="debugLogs.length > 0" type="success" size="small" effect="plain">已完成</el-tag>
          </div>
          <div class="panel-content">
            <div v-if="debugError" class="debug-error">
              <el-alert type="error" :title="`退出码: ${debugExitCode}`" :closable="false" show-icon />
            </div>
            <pre v-if="debugLogs.length > 0" class="debug-logs">{{ debugLogs.join('\n') }}</pre>
            <el-empty v-if="!debugLogs.length && !debugError" description="点击运行按钮开始调试" :image-size="80" />
          </div>
        </div>
      </div>
      <template #footer>
        <el-button v-if="!debugRunning && !debugLogs.length && !debugError" type="primary" @click="handleDebugStart">
          <el-icon><VideoPlay /></el-icon>运行
        </el-button>
        <el-button v-if="debugRunning" type="danger" @click="handleDebugStop">
          <el-icon><VideoPause /></el-icon>停止
        </el-button>
        <el-button v-if="!debugRunning && (debugLogs.length > 0 || debugError)" type="primary" @click="handleDebugStart">
          <el-icon><RefreshRight /></el-icon>重新运行
        </el-button>
        <el-button @click="showDebugDialog = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.scripts-page {
  display: flex;
  height: calc(100vh - 120px);
  gap: 0;
  font-size: 14px;
}

.scripts-sidebar {
  width: 300px;
  min-width: 300px;
  border-right: 1px solid var(--el-border-color-light);
  display: flex;
  flex-direction: column;
  background: var(--el-bg-color);
}

.sidebar-header {
  padding: 10px 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--el-border-color-light);
  flex-shrink: 0;

  .sidebar-title {
    font-weight: 600;
    font-size: 15px;
    white-space: nowrap;
  }

  .sidebar-actions {
    display: flex;
    align-items: center;
    gap: 2px;

    .action-btn {
      width: 28px;
      height: 28px;
      padding: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      border: 1px solid var(--el-border-color);
      background: var(--el-bg-color);
      transition: all 0.3s;

      &:hover {
        border-color: var(--el-color-primary);
        color: var(--el-color-primary);
        background: var(--el-color-primary-light-9);
        transform: translateY(-2px);
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
      }

      &:active {
        transform: translateY(0);
      }
    }
  }
}

.sidebar-tree {
  flex: 1;
  overflow-y: auto;
  padding: 10px;

  :deep(.el-tree-node__content) {
    height: 36px;
    font-size: 14px;
  }

  :deep(.el-tree-node.is-drop-inner > .el-tree-node__content) {
    background: var(--el-color-primary-light-9);
    border-radius: 6px;
    outline: 2px dashed var(--el-color-primary);
    outline-offset: -2px;
  }

  :deep(.el-tree__drop-indicator) {
    display: none;
  }

  :deep(.el-tree-node.is-dragging > .el-tree-node__content) {
    opacity: 0.5;
  }
}

.tree-node {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  overflow: hidden;

  .tree-node-label {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 13px;
  }

  .file-ext-badge {
    font-size: 9px;
    font-weight: 700;
    font-family: var(--dd-font-mono);
    padding: 1px 4px;
    border-radius: 3px;
    background: var(--el-fill-color);
    color: var(--el-text-color-secondary);
    flex-shrink: 0;
    letter-spacing: 0.3px;
    line-height: 1.4;
    opacity: 0;
    transition: opacity 0.2s;
  }

  &:hover .file-ext-badge {
    opacity: 1;
  }

  .tree-node-actions {
    opacity: 0;
    transition: opacity 0.2s;
    flex-shrink: 0;

    .more-btn {
      cursor: pointer;
      padding: 4px;
      border-radius: 4px;
      font-size: 18px;
      color: var(--el-text-color-secondary);
      display: flex;
      align-items: center;
      justify-content: center;
      &:hover {
        background: var(--el-fill-color-light);
        color: var(--el-color-primary);
      }
    }
  }

  &:hover .tree-node-actions {
    opacity: 1;
  }
}

.scripts-editor {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.editor-placeholder {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.editor-header {
  padding: 12px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--el-border-color-light);
  flex-shrink: 0;

  .editor-file-info {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 15px;
  }

  .editor-actions {
    display: flex;
    align-items: center;
    gap: 10px;
  }
}

.editor-content {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;

  .code-editor {
    flex: 1;
    height: 100%;
    min-height: 500px;
  }
}

.binary-notice {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.debug-container {
  display: flex;
  gap: 16px;
  height: 70vh;
  min-height: 500px;
}

.debug-code-panel,
.debug-log-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  overflow: hidden;
  background: var(--el-bg-color);
}

.panel-header {
  padding: 12px 16px;
  background: var(--el-fill-color-light);
  border-bottom: 1px solid var(--el-border-color-light);
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 14px;
  flex-shrink: 0;
}

.panel-content {
  flex: 1;
  overflow: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
}

.debug-error {
  margin-bottom: 12px;
}

.debug-logs {
  font-family: var(--dd-font-mono);
  font-size: 13px;
  line-height: 1.6;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  color: var(--el-text-color-primary);
  flex: 1;
}

:deep(.el-button) {
  font-size: 14px;
}
</style>
