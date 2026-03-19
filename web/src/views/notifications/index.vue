<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { notificationApi, sshKeyApi } from '@/api/notification'
import { ElMessage, ElMessageBox } from 'element-plus'

const activeTab = ref('channels')

const channels = ref<any[]>([])
const channelLoading = ref(false)
const channelTypes = ref<{ type: string; name: string }[]>([])

const showChannelDialog = ref(false)
const isCreateChannel = ref(true)
const channelForm = ref({ id: 0, name: '', type: 'webhook', config: '{}' })

const sshKeys = ref<any[]>([])
const sshKeyLoading = ref(false)

const showSSHKeyDialog = ref(false)
const isCreateSSHKey = ref(true)
const sshKeyForm = ref({ id: 0, name: '', private_key: '' })

const configFields = computed(() => {
  const t = channelForm.value.type
  switch (t) {
    case 'webhook': return [
      { key: 'url', label: 'Webhook URL', type: 'input', placeholder: 'https://example.com/webhook' },
    ]
    case 'email': return [
      { key: 'smtp_host', label: 'SMTP 主机', type: 'input', placeholder: 'smtp.qq.com' },
      { key: 'smtp_port', label: 'SMTP 端口', type: 'input', placeholder: '465' },
      { key: 'smtp_user', label: '邮箱账号', type: 'input', placeholder: 'user@example.com' },
      { key: 'smtp_pass', label: '邮箱密码/授权码', type: 'password', placeholder: 'SMTP 授权码' },
      { key: 'to', label: '收件人', type: 'input', placeholder: '多个收件人用逗号分隔' },
      { key: 'from', label: '发件人 (可选)', type: 'input', placeholder: '留空则使用邮箱账号' },
    ]
    case 'telegram': return [
      { key: 'token', label: 'Bot Token', type: 'input', placeholder: '从 @BotFather 获取' },
      { key: 'chat_id', label: 'Chat ID', type: 'input', placeholder: '聊天/群组 ID' },
      { key: 'api_host', label: 'API 地址 (可选)', type: 'input', placeholder: '自定义 API 地址，留空使用官方' },
      { key: 'proxy', label: '代理地址 (可选)', type: 'input', placeholder: 'http/socks5 代理地址' },
    ]
    case 'dingtalk': return [
      { key: 'webhook', label: 'Webhook URL', type: 'input', placeholder: 'https://oapi.dingtalk.com/robot/send?access_token=xxx' },
      { key: 'secret', label: '加签秘钥 (可选)', type: 'input', placeholder: '安全设置中的 SEC 开头的秘钥' },
    ]
    case 'wecom': return [
      { key: 'webhook', label: 'Webhook URL', type: 'input', placeholder: 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx' },
    ]
    case 'bark': return [
      { key: 'key', label: 'Device Key', type: 'input', placeholder: 'Bark App 中的推送 Key' },
      { key: 'server', label: '服务器 (可选)', type: 'input', placeholder: '默认 https://api.day.app' },
      { key: 'sound', label: '推送声音 (可选)', type: 'input', placeholder: '如 birdsong，留空使用默认' },
      { key: 'group', label: '推送分组 (可选)', type: 'input', placeholder: '消息分组名称' },
      { key: 'icon', label: '图标 URL (可选)', type: 'input', placeholder: 'https://example.com/icon.png' },
      { key: 'level', label: '时效性 (可选)', type: 'select', placeholder: '推送优先级', options: [
        { label: '默认 (active)', value: 'active' },
        { label: '时效性 (timeSensitive)', value: 'timeSensitive' },
        { label: '被动 (passive)', value: 'passive' },
      ]},
      { key: 'url', label: '跳转 URL (可选)', type: 'input', placeholder: '点击通知后跳转的链接' },
    ]
    case 'pushplus': return [
      { key: 'token', label: 'Token', type: 'input', placeholder: 'PushPlus 用户 Token' },
      { key: 'topic', label: '群组编码 (可选)', type: 'input', placeholder: '一对多推送时的群组编码' },
      { key: 'template', label: '模板 (可选)', type: 'select', placeholder: '消息模板', options: [
        { label: '默认 (html)', value: 'html' },
        { label: 'JSON', value: 'json' },
        { label: '纯文本', value: 'txt' },
        { label: 'Markdown', value: 'markdown' },
      ]},
    ]
    case 'serverchan': return [
      { key: 'key', label: 'SendKey', type: 'input', placeholder: 'Server酱的 SendKey (SCT...)' },
    ]
    case 'feishu': return [
      { key: 'webhook', label: 'Webhook URL', type: 'input', placeholder: 'https://open.feishu.cn/open-apis/bot/v2/hook/xxx' },
      { key: 'secret', label: '加签秘钥 (可选)', type: 'input', placeholder: '安全设置中的签名校验秘钥' },
    ]
    case 'gotify': return [
      { key: 'server', label: '服务器地址', type: 'input', placeholder: 'https://gotify.example.com' },
      { key: 'token', label: 'App Token', type: 'input', placeholder: 'Gotify 应用 Token' },
      { key: 'priority', label: '优先级 (可选)', type: 'input', placeholder: '0-10，默认 5' },
    ]
    case 'pushdeer': return [
      { key: 'key', label: 'PushKey', type: 'input', placeholder: 'PushDeer 的 PushKey' },
      { key: 'server', label: '服务器 (可选)', type: 'input', placeholder: '默认 https://api2.pushdeer.com' },
    ]
    case 'chanify': return [
      { key: 'token', label: 'Token', type: 'input', placeholder: 'Chanify 设备 Token' },
      { key: 'server', label: '服务器 (可选)', type: 'input', placeholder: '默认 https://api.chanify.net' },
    ]
    case 'igot': return [
      { key: 'key', label: 'Key', type: 'input', placeholder: 'iGot 推送 Key' },
    ]
    case 'pushover': return [
      { key: 'token', label: 'API Token', type: 'input', placeholder: '应用 API Token' },
      { key: 'user', label: 'User Key', type: 'input', placeholder: '用户 Key' },
    ]
    case 'discord': return [
      { key: 'webhook', label: 'Webhook URL', type: 'input', placeholder: 'https://discord.com/api/webhooks/...' },
    ]
    case 'slack': return [
      { key: 'webhook', label: 'Webhook URL', type: 'input', placeholder: 'https://hooks.slack.com/services/...' },
    ]
    case 'ntfy': return [
      { key: 'topic', label: 'Topic', type: 'input', placeholder: '订阅主题名称' },
      { key: 'server', label: '服务器 (可选)', type: 'input', placeholder: '默认 https://ntfy.sh' },
      { key: 'token', label: 'Token (可选)', type: 'input', placeholder: '访问令牌，用于私有主题' },
      { key: 'priority', label: '优先级 (可选)', type: 'select', placeholder: '消息优先级', options: [
        { label: '最低 (1)', value: '1' },
        { label: '低 (2)', value: '2' },
        { label: '默认 (3)', value: '3' },
        { label: '高 (4)', value: '4' },
        { label: '紧急 (5)', value: '5' },
      ]},
    ]
    case 'custom': return [
      { key: 'url', label: 'URL', type: 'input', placeholder: 'https://example.com/api/notify' },
      { key: 'method', label: 'Method', type: 'select', placeholder: '请求方法', options: [
        { label: 'POST', value: 'POST' },
        { label: 'GET', value: 'GET' },
        { label: 'PUT', value: 'PUT' },
      ]},
      { key: 'content_type', label: 'Content-Type', type: 'input', placeholder: '默认 application/json' },
      { key: 'headers', label: 'Headers (JSON)', type: 'textarea', placeholder: '{"Authorization": "Bearer xxx"}' },
      { key: 'body', label: 'Body 模板', type: 'textarea', placeholder: '使用 {{title}} 和 {{content}} 作为占位符' },
    ]
    default: return [{ key: 'url', label: 'URL', type: 'input', placeholder: '' }]
  }
})

const configData = ref<Record<string, string>>({})

function syncConfigToForm() {
  channelForm.value.config = JSON.stringify(configData.value)
}

function syncFormToConfig() {
  try {
    configData.value = JSON.parse(channelForm.value.config)
  } catch {
    configData.value = {}
  }
}

async function loadChannels() {
  channelLoading.value = true
  try {
    const res = await notificationApi.list()
    channels.value = res.data || []
  } catch {
    ElMessage.error('加载通知渠道失败')
  } finally {
    channelLoading.value = false
  }
}

async function loadChannelTypes() {
  try {
    const res = await notificationApi.types()
    channelTypes.value = res.data || []
  } catch { /* ignore */ }
}

async function loadSSHKeys() {
  sshKeyLoading.value = true
  try {
    const res = await sshKeyApi.list()
    sshKeys.value = res.data || []
  } catch {
    ElMessage.error('加载 SSH 密钥失败')
  } finally {
    sshKeyLoading.value = false
  }
}

onMounted(() => {
  loadChannels()
  loadChannelTypes()
  loadSSHKeys()
})

function openCreateChannel() {
  isCreateChannel.value = true
  channelForm.value = { id: 0, name: '', type: 'webhook', config: '{}' }
  configData.value = {}
  showChannelDialog.value = true
}

function openEditChannel(row: any) {
  isCreateChannel.value = false
  channelForm.value = { id: row.id, name: row.name, type: row.type, config: row.config || '{}' }
  syncFormToConfig()
  showChannelDialog.value = true
}

async function handleSaveChannel() {
  if (!channelForm.value.name.trim()) {
    ElMessage.warning('名称不能为空')
    return
  }
  syncConfigToForm()
  try {
    if (isCreateChannel.value) {
      await notificationApi.create(channelForm.value)
      ElMessage.success('创建成功')
    } else {
      await notificationApi.update(channelForm.value.id, channelForm.value)
      ElMessage.success('更新成功')
    }
    showChannelDialog.value = false
    loadChannels()
  } catch {
    ElMessage.error(isCreateChannel.value ? '创建失败' : '更新失败')
  }
}

async function handleDeleteChannel(id: number) {
  try {
    await ElMessageBox.confirm('确定要删除该通知渠道吗？', '确认删除', { type: 'warning' })
    await notificationApi.delete(id)
    ElMessage.success('删除成功')
    loadChannels()
  } catch { /* cancelled */ }
}

async function handleToggleChannel(row: any) {
  try {
    if (row.enabled) {
      await notificationApi.disable(row.id)
    } else {
      await notificationApi.enable(row.id)
    }
    loadChannels()
  } catch {
    ElMessage.error('操作失败')
  }
}

async function handleTestChannel(id: number) {
  try {
    await notificationApi.test(id)
    ElMessage.success('测试通知发送成功')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || '测试发送失败')
  }
}

function getTypeName(type: string) {
  const found = channelTypes.value.find(t => t.type === type)
  return found?.name || type
}

function openCreateSSHKey() {
  isCreateSSHKey.value = true
  sshKeyForm.value = { id: 0, name: '', private_key: '' }
  showSSHKeyDialog.value = true
}

function openEditSSHKey(row: any) {
  isCreateSSHKey.value = false
  sshKeyForm.value = { id: row.id, name: row.name, private_key: '' }
  showSSHKeyDialog.value = true
}

async function handleSaveSSHKey() {
  if (!sshKeyForm.value.name.trim()) {
    ElMessage.warning('名称不能为空')
    return
  }
  if (isCreateSSHKey.value && !sshKeyForm.value.private_key.trim()) {
    ElMessage.warning('私钥不能为空')
    return
  }
  try {
    const data: any = { name: sshKeyForm.value.name }
    if (sshKeyForm.value.private_key) {
      data.private_key = sshKeyForm.value.private_key
    }
    if (isCreateSSHKey.value) {
      await sshKeyApi.create(data)
      ElMessage.success('创建成功')
    } else {
      await sshKeyApi.update(sshKeyForm.value.id, data)
      ElMessage.success('更新成功')
    }
    showSSHKeyDialog.value = false
    loadSSHKeys()
  } catch {
    ElMessage.error(isCreateSSHKey.value ? '创建失败' : '更新失败')
  }
}

async function handleDeleteSSHKey(id: number) {
  try {
    await ElMessageBox.confirm('确定要删除该 SSH 密钥吗？', '确认删除', { type: 'warning' })
    await sshKeyApi.delete(id)
    ElMessage.success('删除成功')
    loadSSHKeys()
  } catch { /* cancelled */ }
}
</script>

<template>
  <div class="notifications-page">
    <div class="page-header-block">
      <h2>通知渠道</h2>
      <span class="page-subtitle">配置任务执行结果通知和 SSH 密钥管理</span>
    </div>
    <el-tabs v-model="activeTab">
      <el-tab-pane label="通知渠道" name="channels">
        <div class="tab-header">
          <el-button type="primary" @click="openCreateChannel">
            <el-icon><Plus /></el-icon>新建渠道
          </el-button>
        </div>

        <el-table :data="channels" v-loading="channelLoading" stripe>
          <el-table-column prop="name" label="名称" min-width="150" />
          <el-table-column prop="type" label="类型" width="120">
            <template #default="{ row }">
              <el-tag size="small" effect="plain">{{ getTypeName(row.type) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="启用" width="80" align="center">
            <template #default="{ row }">
              <el-switch :model-value="row.enabled" size="small" @change="handleToggleChannel(row)" />
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="170">
            <template #default="{ row }">{{ new Date(row.created_at).toLocaleString() }}</template>
          </el-table-column>
          <el-table-column label="操作" width="200" fixed="right">
            <template #default="{ row }">
              <el-button size="small" text type="success" @click="handleTestChannel(row.id)">测试</el-button>
              <el-button size="small" text type="primary" @click="openEditChannel(row)">编辑</el-button>
              <el-button size="small" text type="danger" @click="handleDeleteChannel(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="SSH 密钥" name="ssh-keys">
        <div class="tab-header">
          <el-button type="primary" @click="openCreateSSHKey">
            <el-icon><Plus /></el-icon>新建密钥
          </el-button>
        </div>

        <el-table :data="sshKeys" v-loading="sshKeyLoading" stripe>
          <el-table-column prop="name" label="名称" min-width="200" />
          <el-table-column prop="created_at" label="创建时间" width="170">
            <template #default="{ row }">{{ new Date(row.created_at).toLocaleString() }}</template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button size="small" text type="primary" @click="openEditSSHKey(row)">编辑</el-button>
              <el-button size="small" text type="danger" @click="handleDeleteSSHKey(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="showChannelDialog" :title="isCreateChannel ? '新建通知渠道' : '编辑通知渠道'" width="600px">
      <el-form :model="channelForm" label-width="130px">
        <el-form-item label="名称">
          <el-input v-model="channelForm.name" placeholder="渠道名称" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="channelForm.type" style="width: 100%" @change="configData = {}">
            <el-option v-for="t in channelTypes" :key="t.type" :label="t.name" :value="t.type" />
          </el-select>
        </el-form-item>
        <el-divider content-position="left">配置</el-divider>
        <el-form-item v-for="field in configFields" :key="field.key" :label="field.label">
          <el-select
            v-if="field.type === 'select'"
            v-model="configData[field.key]"
            :placeholder="field.placeholder || field.label"
            clearable
            style="width: 100%"
          >
            <el-option v-for="opt in field.options" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
          <el-input
            v-else-if="field.type === 'textarea'"
            v-model="configData[field.key]"
            type="textarea"
            :rows="3"
            :placeholder="field.placeholder || field.label"
          />
          <el-input
            v-else
            v-model="configData[field.key]"
            :type="field.type === 'password' ? 'password' : 'text'"
            :show-password="field.type === 'password'"
            :placeholder="field.placeholder || field.label"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showChannelDialog = false">取消</el-button>
        <el-button type="primary" @click="handleSaveChannel">{{ isCreateChannel ? '创建' : '保存' }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showSSHKeyDialog" :title="isCreateSSHKey ? '新建 SSH 密钥' : '编辑 SSH 密钥'" width="550px">
      <el-form :model="sshKeyForm" label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="sshKeyForm.name" placeholder="密钥名称" />
        </el-form-item>
        <el-form-item label="私钥">
          <el-input
            v-model="sshKeyForm.private_key"
            type="textarea"
            :rows="8"
            :placeholder="isCreateSSHKey ? '粘贴 SSH 私钥内容' : '留空不修改'"
            spellcheck="false"
            style="font-family: monospace"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showSSHKeyDialog = false">取消</el-button>
        <el-button type="primary" @click="handleSaveSSHKey">{{ isCreateSSHKey ? '创建' : '保存' }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.notifications-page {
  padding: 0;
}

.page-header-block {
  margin-bottom: 16px;

  h2 { margin: 0; font-size: 20px; font-weight: 700; color: var(--el-text-color-primary); }

  .page-subtitle {
    font-size: 13px;
    color: var(--el-text-color-secondary);
    display: block;
    margin-top: 2px;
  }
}

.tab-header {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 16px;
}
</style>
