<script setup lang="ts">
import { ref, watch } from 'vue'
import CronInput from './CronInput.vue'

const props = defineProps<{
  visible: boolean
  task?: any
  prefill?: any
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  'submit': [data: any]
}>()

const form = ref({
  name: '',
  command: '',
  cron_expression: '* * * * *',
  timeout: 86400,
  max_retries: 0,
  retry_interval: 60,
  notify_on_failure: true,
  notify_on_success: false,
  labels: [] as string[],
  depends_on: null as number | null,
  task_before: '',
  task_after: '',
  allow_multiple_instances: false,
})

const labelInput = ref('')
const activeTab = ref('basic')

watch(() => props.visible, (val) => {
  if (val && props.task) {
    form.value = {
      name: props.task.name || '',
      command: props.task.command || '',
      cron_expression: props.task.cron_expression || '* * * * *',
      timeout: props.task.timeout ?? 86400,
      max_retries: props.task.max_retries ?? 0,
      retry_interval: props.task.retry_interval ?? 60,
      notify_on_failure: props.task.notify_on_failure ?? true,
      notify_on_success: props.task.notify_on_success ?? false,
      labels: props.task.labels || [],
      depends_on: props.task.depends_on || null,
      task_before: props.task.task_before || '',
      task_after: props.task.task_after || '',
      allow_multiple_instances: props.task.allow_multiple_instances ?? false,
    }
  } else if (val) {
    const p = props.prefill
    form.value = {
      name: p?.name || '', command: p?.command || '',
      cron_expression: p?.cron_expression || '* * * * *',
      timeout: 86400, max_retries: 0, retry_interval: 60,
      notify_on_failure: true, notify_on_success: false, labels: [], depends_on: null,
      task_before: '', task_after: '', allow_multiple_instances: false,
    }
  }
  activeTab.value = 'basic'
})

function addLabel() {
  const val = labelInput.value.trim()
  if (val && !form.value.labels.includes(val)) {
    form.value.labels.push(val)
  }
  labelInput.value = ''
}

function removeLabel(label: string) {
  form.value.labels = form.value.labels.filter(l => l !== label)
}

function handleSubmit() {
  if (!form.value.name || !form.value.command || !form.value.cron_expression) return
  const data = { ...form.value }
  if (!data.task_before) data.task_before = ''
  if (!data.task_after) data.task_after = ''
  emit('submit', data)
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    :title="task ? '编辑任务' : '新建任务'"
    width="640px"
    destroy-on-close
    @update:model-value="emit('update:visible', $event)"
  >
    <el-tabs v-model="activeTab">
      <el-tab-pane label="基本信息" name="basic">
        <el-form :model="form" label-width="100px">
          <el-form-item label="任务名称" required>
            <el-input v-model="form.name" placeholder="任务名称" />
          </el-form-item>
          <el-form-item label="执行命令" required>
            <el-input v-model="form.command" placeholder="如: script.py 或 python3 script.py" />
            <div style="font-size: 12px; color: var(--el-text-color-secondary); margin-top: 4px">
              支持 task 脚本名 格式,自动根据扩展名选择解释器 (.py/.js/.ts/.sh)
            </div>
          </el-form-item>
          <el-form-item label="定时规则" required>
            <CronInput v-model="form.cron_expression" />
          </el-form-item>
          <el-form-item label="标签">
            <div class="label-area">
              <el-tag
                v-for="label in form.labels"
                :key="label"
                closable
                @close="removeLabel(label)"
              >{{ label }}</el-tag>
              <el-input
                v-model="labelInput"
                size="small"
                style="width: 120px"
                placeholder="添加标签"
                @keyup.enter="addLabel"
              />
            </div>
          </el-form-item>
        </el-form>
      </el-tab-pane>

      <el-tab-pane label="高级设置" name="advanced">
        <el-form :model="form" label-width="120px">
          <el-form-item label="超时(秒)">
            <el-input-number v-model="form.timeout" :min="0" :max="86400" />
          </el-form-item>
          <el-form-item label="最大重试次数">
            <el-input-number v-model="form.max_retries" :min="0" :max="10" />
          </el-form-item>
          <el-form-item label="重试间隔(秒)">
            <el-input-number v-model="form.retry_interval" :min="0" :max="3600" />
          </el-form-item>
          <el-form-item label="依赖任务ID">
            <el-input-number v-model="form.depends_on" :min="0" controls-position="right" placeholder="可选" />
          </el-form-item>
          <el-form-item label="失败时通知">
            <el-switch v-model="form.notify_on_failure" />
          </el-form-item>
          <el-form-item label="成功时通知">
            <el-switch v-model="form.notify_on_success" />
            <span style="font-size: 12px; color: var(--el-text-color-secondary); margin-left: 8px">任务执行成功后发送通知</span>
          </el-form-item>
          <el-form-item label="允许多实例">
            <el-switch v-model="form.allow_multiple_instances" />
          </el-form-item>
        </el-form>
      </el-tab-pane>

      <el-tab-pane label="钩子脚本" name="hooks">
        <el-form :model="form" label-width="100px">
          <el-form-item label="前置脚本">
            <el-input v-model="form.task_before" type="textarea" :rows="4" placeholder="任务执行前运行的 shell 脚本" />
          </el-form-item>
          <el-form-item label="后置脚本">
            <el-input v-model="form.task_after" type="textarea" :rows="4" placeholder="任务执行后运行的 shell 脚本" />
          </el-form-item>
        </el-form>
      </el-tab-pane>
    </el-tabs>

    <template #footer>
      <el-button @click="emit('update:visible', false)">取消</el-button>
      <el-button type="primary" @click="handleSubmit">{{ task ? '更新' : '创建' }}</el-button>
    </template>
  </el-dialog>
</template>

<style scoped lang="scss">
.label-area {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}
</style>
