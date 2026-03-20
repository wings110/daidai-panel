<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { logApi } from '@/api/log'
import { taskApi } from '@/api/task'
import { useAuthStore } from '@/stores/auth'
import { ElMessage, ElMessageBox } from 'element-plus'

const logs = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const taskIdFilter = ref<string>('')
const statusFilter = ref<string>('')
const keyword = ref('')
const loading = ref(false)
const detailVisible = ref(false)
const detailContent = ref('')
const detailLog = ref<any>(null)
const selectedIds = ref<number[]>([])
const autoRefresh = ref(true)
let refreshTimer: ReturnType<typeof setInterval> | null = null
let logEventSource: EventSource | null = null
const logContentRef = ref<HTMLElement>()
let sseBuffer: string[] = []
let sseFlushRaf = 0

const showFileBrowser = ref(false)
const currentTaskId = ref<number>(0)
const logFiles = ref<any[]>([])
const logFilesLoading = ref(false)
const showFileContent = ref(false)
const fileContentData = ref('')
const fileContentName = ref('')

async function loadLogs() {
  loading.value = true
  try {
    const params: any = { page: page.value, page_size: pageSize.value }
    if (taskIdFilter.value) params.task_id = taskIdFilter.value
    if (statusFilter.value !== '') params.status = statusFilter.value
    if (keyword.value) params.keyword = keyword.value
    const res = await logApi.list(params)
    logs.value = res.data
    total.value = res.total
  } catch {
    ElMessage.error('加载日志失败')
  } finally {
    loading.value = false
  }
}

function hasRunningLogs() {
  return logs.value.some(l => l.status === 2)
}

function startAutoRefresh() {
  stopAutoRefresh()
  refreshTimer = setInterval(async () => {
    await loadLogs()
    if (!hasRunningLogs()) {
      stopAutoRefresh()
    }
  }, 5000)
}

function stopAutoRefresh() {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
}

onMounted(async () => {
  await loadLogs()
  if (autoRefresh.value && hasRunningLogs()) {
    startAutoRefresh()
  }
})

function handleSearch() {
  page.value = 1
  loadLogs()
}

function getStatusType(status: number | null) {
  if (status === 2) return 'warning'
  if (status === 0) return 'success'
  if (status === 1) return 'danger'
  return 'info'
}

function getStatusText(status: number | null) {
  if (status === 2) return '运行中'
  if (status === 0) return '成功'
  if (status === 1) return '失败'
  return '未知'
}

function formatDuration(d: number | null) {
  if (d == null) return '-'
  if (d < 60) return `${d.toFixed(1)}s`
  return `${Math.floor(d / 60)}m ${(d % 60).toFixed(0)}s`
}

function formatTime(t: string | null) {
  if (!t) return '-'
  return new Date(t).toLocaleString()
}

async function viewDetail(log: any) {
  detailLog.value = log
  detailContent.value = ''
  detailVisible.value = true
  closeLogSSE()

  if (log.status === 2) {
    const authStore = useAuthStore()
    const url = `/api/v1/logs/${log.id}/stream?token=${authStore.accessToken}`
    logEventSource = new EventSource(url)
    sseBuffer = []
    logEventSource.onmessage = (e) => {
      sseBuffer.push(e.data)
      if (!sseFlushRaf) {
        sseFlushRaf = requestAnimationFrame(() => {
          detailContent.value += sseBuffer.join('\n') + '\n'
          sseBuffer = []
          sseFlushRaf = 0
          if (logContentRef.value) {
            logContentRef.value.scrollTop = logContentRef.value.scrollHeight
          }
        })
      }
    }
    logEventSource.addEventListener('done', () => {
      closeLogSSE()
      loadLogs()
    })
    logEventSource.onerror = () => {
      closeLogSSE()
    }
  } else {
    try {
      const res = await logApi.detail(log.id)
      detailLog.value = res
      detailContent.value = res.content || '(无日志内容)'
    } catch {
      ElMessage.error('获取日志详情失败')
    }
  }
}

function closeLogSSE() {
  if (logEventSource) {
    logEventSource.close()
    logEventSource = null
  }
}

async function handleDelete(log: any) {
  await ElMessageBox.confirm('确定删除此日志记录？', '确认', { type: 'warning' })
  try {
    await logApi.delete(log.id)
    ElMessage.success('已删除')
    loadLogs()
  } catch {
    ElMessage.error('删除失败')
  }
}

async function handleClean() {
  await ElMessageBox.confirm('确定清理 7 天前的日志记录？', '清理日志', { type: 'warning' })
  try {
    const res = await logApi.clean(7)
    ElMessage.success(res.message)
    loadLogs()
  } catch {
    ElMessage.error('清理失败')
  }
}

function handleSelectionChange(rows: any[]) {
  selectedIds.value = rows.map(r => r.id)
}

async function handleBatchDelete() {
  if (selectedIds.value.length === 0) return
  try {
    await ElMessageBox.confirm(`确定删除选中的 ${selectedIds.value.length} 条日志？`, '批量删除', { type: 'warning' })
    await logApi.batchDelete(selectedIds.value)
    ElMessage.success('批量删除成功')
    selectedIds.value = []
    loadLogs()
  } catch (err: any) {
    if (err !== 'cancel' && err?.toString() !== 'cancel') {
      ElMessage.error(err?.response?.data?.error || '批量删除失败')
    }
  }
}

function toggleAutoRefresh() {
  autoRefresh.value = !autoRefresh.value
  if (autoRefresh.value) {
    loadLogs()
    startAutoRefresh()
  } else {
    stopAutoRefresh()
  }
}

async function browseLogFiles(log: any) {
  currentTaskId.value = log.task_id
  logFiles.value = []
  showFileBrowser.value = true
  logFilesLoading.value = true
  try {
    const res = await taskApi.logFiles(log.task_id)
    logFiles.value = res || []
  } catch {
    ElMessage.error('获取日志文件列表失败')
  } finally {
    logFilesLoading.value = false
  }
}

async function viewLogFile(file: any) {
  try {
    const res = await taskApi.logFileContent(currentTaskId.value, file.filename)
    fileContentData.value = res.content || '(空文件)'
    fileContentName.value = file.filename
    showFileContent.value = true
  } catch {
    ElMessage.error('读取日志文件失败')
  }
}

async function deleteLogFile(file: any) {
  await ElMessageBox.confirm(`确定删除日志文件 ${file.filename}？`, '确认', { type: 'warning' })
  try {
    await taskApi.deleteLogFile(currentTaskId.value, file.filename)
    ElMessage.success('已删除')
    logFiles.value = logFiles.value.filter((f: any) => f.filename !== file.filename)
  } catch {
    ElMessage.error('删除失败')
  }
}

function formatFileSize(size: number) {
  if (size < 1024) return size + ' B'
  if (size < 1024 * 1024) return (size / 1024).toFixed(1) + ' KB'
  return (size / 1024 / 1024).toFixed(1) + ' MB'
}

onBeforeUnmount(() => {
  stopAutoRefresh()
  closeLogSSE()
  if (sseFlushRaf) {
    cancelAnimationFrame(sseFlushRaf)
    sseFlushRaf = 0
  }
})
</script>

<template>
  <div class="logs-page">
    <div class="page-header">
      <div>
        <h2>执行日志</h2>
        <span class="page-subtitle">查看所有任务的历史执行记录</span>
      </div>
      <div style="display: flex; gap: 8px; align-items: center">
        <el-button @click="toggleAutoRefresh" :type="autoRefresh ? 'primary' : 'default'">
          <el-icon><Refresh /></el-icon> {{ autoRefresh ? '停止刷新' : '自动刷新' }}
        </el-button>
        <el-button @click="handleBatchDelete" :disabled="selectedIds.length === 0">
          <el-icon><Delete /></el-icon> 批量删除
        </el-button>
        <el-button type="danger" plain @click="handleClean">
          <el-icon><Delete /></el-icon> 清理日志
        </el-button>
      </div>
    </div>

    <div class="filter-bar">
      <el-input v-model="keyword" placeholder="搜索日志内容" clearable style="width: 220px" @keyup.enter="handleSearch" @clear="handleSearch">
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-input v-model="taskIdFilter" placeholder="任务ID" clearable style="width: 120px" @change="handleSearch" />
      <el-select v-model="statusFilter" placeholder="状态" clearable style="width: 120px" @change="handleSearch">
        <el-option label="成功" value="0" />
        <el-option label="失败" value="1" />
        <el-option label="运行中" value="2" />
      </el-select>
    </div>

    <el-table v-loading="loading" :data="logs" stripe @selection-change="handleSelectionChange">
      <el-table-column type="selection" width="40" />
      <el-table-column label="ID" prop="id" width="70" />
      <el-table-column label="任务" min-width="150">
        <template #default="{ row }">{{ row.task_name || `任务#${row.task_id}` }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100" align="center">
        <template #default="{ row }">
          <el-tag :type="getStatusType(row.status)" size="small" :class="row.status === 2 ? 'tag-with-dot' : ''">
            <span v-if="row.status === 2" class="pulse-dot"></span>
            {{ getStatusText(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="耗时" width="100" align="center">
        <template #default="{ row }">{{ formatDuration(row.duration) }}</template>
      </el-table-column>
      <el-table-column label="开始时间" width="180">
        <template #default="{ row }">{{ formatTime(row.started_at) }}</template>
      </el-table-column>
      <el-table-column label="结束时间" width="180">
        <template #default="{ row }">{{ formatTime(row.ended_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <div class="action-group">
            <el-tooltip content="查看日志" placement="top">
              <el-button size="small" type="primary" plain circle @click="viewDetail(row)">
                <el-icon><View /></el-icon>
              </el-button>
            </el-tooltip>
            <el-tooltip content="日志文件" placement="top">
              <el-button size="small" type="info" plain circle @click="browseLogFiles(row)">
                <el-icon><Folder /></el-icon>
              </el-button>
            </el-tooltip>
            <el-tooltip content="删除" placement="top">
              <el-button size="small" type="danger" plain circle @click="handleDelete(row)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </el-tooltip>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-bar">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @current-change="loadLogs"
        @size-change="loadLogs"
      />
    </div>

    <el-dialog v-model="detailVisible" title="日志详情" width="800px" destroy-on-close @close="closeLogSSE">
      <div v-if="detailLog" class="log-meta">
        <el-descriptions :column="3" size="small" border>
          <el-descriptions-item label="任务">{{ detailLog.task_name }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(detailLog.status)" size="small">{{ getStatusText(detailLog.status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="耗时">{{ formatDuration(detailLog.duration) }}</el-descriptions-item>
          <el-descriptions-item label="开始时间">{{ formatTime(detailLog.started_at) }}</el-descriptions-item>
          <el-descriptions-item label="结束时间">{{ formatTime(detailLog.ended_at) }}</el-descriptions-item>
        </el-descriptions>
      </div>
      <pre ref="logContentRef" class="log-content">{{ detailContent }}</pre>
    </el-dialog>

    <el-dialog v-model="showFileBrowser" title="日志文件" width="650px">
      <el-table :data="logFiles" v-loading="logFilesLoading" max-height="400px" size="small">
        <el-table-column prop="filename" label="文件名" min-width="200" />
        <el-table-column label="大小" width="100">
          <template #default="{ row }">{{ formatFileSize(row.size) }}</template>
        </el-table-column>
        <el-table-column label="时间" width="180">
          <template #default="{ row }">{{ new Date(row.created_at).toLocaleString() }}</template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" text size="small" @click="viewLogFile(row)">查看</el-button>
            <el-button type="danger" text size="small" @click="deleteLogFile(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!logFilesLoading && logFiles.length === 0" description="暂无日志文件" />
    </el-dialog>

    <el-dialog v-model="showFileContent" :title="fileContentName" width="800px">
      <pre class="log-content">{{ fileContentData }}</pre>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.logs-page {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;

  h2 { margin: 0; font-size: 20px; font-weight: 700; color: var(--el-text-color-primary); }

  .page-subtitle {
    font-size: 13px;
    color: var(--el-text-color-secondary);
    display: block;
    margin-top: 2px;
  }
}

:deep(.tag-with-dot) {
  display: inline-flex !important;
  align-items: center;
  gap: 5px;
}

.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.pagination-bar {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.log-meta {
  margin-bottom: 16px;
}

.action-group {
  display: flex;
  align-items: center;
  gap: 6px;
}

.log-content {
  background: var(--el-fill-color-darker);
  color: var(--el-text-color-primary);
  padding: 16px;
  border-radius: 6px;
  max-height: 500px;
  overflow: auto;
  font-family: var(--dd-font-mono);
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
}
</style>
