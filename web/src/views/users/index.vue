<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { userApi } from '@/api/security'
import { useAuthStore } from '@/stores/auth'
import { ElMessage, ElMessageBox } from 'element-plus'

const authStore = useAuthStore()
const users = ref<any[]>([])
const loading = ref(false)

const showCreateDialog = ref(false)
const showResetPwdDialog = ref(false)

const createForm = ref({ username: '', password: '', role: 'operator' })
const resetPwdForm = ref({ id: 0, username: '', password: '' })

async function loadUsers() {
  loading.value = true
  try {
    const res = await userApi.list()
    users.value = res.data || []
  } catch {
    ElMessage.error('加载用户列表失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadUsers)

function openCreate() {
  createForm.value = { username: '', password: '', role: 'operator' }
  showCreateDialog.value = true
}

async function handleCreate() {
  if (!createForm.value.username.trim() || !createForm.value.password.trim()) {
    ElMessage.warning('用户名和密码不能为空')
    return
  }
  try {
    await userApi.create(createForm.value)
    ElMessage.success('创建成功')
    showCreateDialog.value = false
    loadUsers()
  } catch {
    ElMessage.error('创建失败')
  }
}

async function handleToggle(row: any) {
  try {
    await userApi.update(row.id, { enabled: !row.enabled })
    loadUsers()
  } catch {
    ElMessage.error('操作失败')
  }
}

async function handleRoleChange(row: any, role: string) {
  try {
    await userApi.update(row.id, { role })
    ElMessage.success('角色更新成功')
    loadUsers()
  } catch {
    ElMessage.error('更新失败')
  }
}

async function handleDelete(row: any) {
  try {
    await ElMessageBox.confirm(`确定要删除用户 ${row.username} 吗？`, '确认删除', { type: 'warning' })
    await userApi.delete(row.id)
    ElMessage.success('删除成功')
    loadUsers()
  } catch { /* cancelled */ }
}

function openResetPassword(row: any) {
  resetPwdForm.value = { id: row.id, username: row.username, password: '' }
  showResetPwdDialog.value = true
}

async function handleResetPassword() {
  if (!resetPwdForm.value.password.trim()) {
    ElMessage.warning('密码不能为空')
    return
  }
  try {
    await userApi.resetPassword(resetPwdForm.value.id, resetPwdForm.value.password)
    ElMessage.success('密码重置成功')
    showResetPwdDialog.value = false
  } catch {
    ElMessage.error('重置失败')
  }
}

function getRoleTag(role: string) {
  switch (role) {
    case 'admin': return 'danger'
    case 'operator': return ''
    case 'viewer': return 'info'
    default: return 'info'
  }
}

function getRoleName(role: string) {
  switch (role) {
    case 'admin': return '管理员'
    case 'operator': return '操作员'
    case 'viewer': return '观察者'
    default: return role
  }
}
</script>

<template>
  <div class="users-page">
    <div class="page-header">
      <div>
        <h2>用户管理</h2>
        <span class="page-subtitle">管理系统用户账户及权限角色</span>
      </div>
      <el-button type="primary" @click="openCreate">
        <el-icon><Plus /></el-icon>新建用户
      </el-button>
    </div>

    <el-table :data="users" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="username" label="用户名" min-width="150" />
      <el-table-column prop="role" label="角色" width="140">
        <template #default="{ row }">
          <el-select
            :model-value="row.role"
            size="small"
            :disabled="row.username === authStore.user?.username"
            @change="(val: string) => handleRoleChange(row, val)"
          >
            <el-option value="admin" label="管理员" />
            <el-option value="operator" label="操作员" />
            <el-option value="viewer" label="观察者" />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80" align="center">
        <template #default="{ row }">
          <el-switch
            :model-value="row.enabled"
            size="small"
            :disabled="row.username === authStore.user?.username"
            @change="handleToggle(row)"
          />
        </template>
      </el-table-column>
      <el-table-column prop="last_login_at" label="最后登录" width="170">
        <template #default="{ row }">
          {{ row.last_login_at ? new Date(row.last_login_at).toLocaleString() : '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="170">
        <template #default="{ row }">{{ new Date(row.created_at).toLocaleString() }}</template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button size="small" text type="primary" @click="openResetPassword(row)">重置密码</el-button>
          <el-button
            size="small" text type="danger"
            :disabled="row.username === authStore.user?.username"
            @click="handleDelete(row)"
          >删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="showCreateDialog" title="新建用户" width="400px">
      <el-form :model="createForm" label-width="80px">
        <el-form-item label="用户名">
          <el-input v-model="createForm.username" placeholder="3-32 位字母/数字/下划线" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="createForm.password" type="password" show-password placeholder="6 位以上" />
        </el-form-item>
        <el-form-item label="角色">
          <el-radio-group v-model="createForm.role">
            <el-radio value="admin">管理员</el-radio>
            <el-radio value="operator">操作员</el-radio>
            <el-radio value="viewer">观察者</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showResetPwdDialog" title="重置密码" width="400px">
      <el-form :model="resetPwdForm" label-width="80px">
        <el-form-item label="用户">
          <el-input :model-value="resetPwdForm.username" disabled />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="resetPwdForm.password" type="password" show-password placeholder="6 位以上" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showResetPwdDialog = false">取消</el-button>
        <el-button type="primary" @click="handleResetPassword">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.users-page {
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
</style>
