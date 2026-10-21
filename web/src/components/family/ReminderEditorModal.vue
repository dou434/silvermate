<template>
  <a-modal
    :open="open"
    :title="isEdit ? '修改提醒' : '新建提醒'"
    :confirm-loading="saving"
    ok-text="保存"
    cancel-text="取消"
    width="520px"
    @ok="handleSubmit"
    @cancel="handleCancel"
  >
    <a-form :model="form" layout="vertical" class="reminder-form">
      <a-form-item label="提醒什么" required>
        <a-input v-model:value="form.title" size="large" placeholder="例如：吃降压药" :maxlength="120" />
      </a-form-item>

      <a-form-item label="什么时候提醒" required>
        <a-date-picker
          v-model:value="form.remindAt"
          show-time
          format="YYYY-MM-DD HH:mm"
          size="large"
          style="width: 100%"
          placeholder="选择日期和时间"
        />
      </a-form-item>

      <a-form-item label="重复">
        <a-radio-group v-model:value="form.repeatType" size="large">
          <a-radio-button value="none">只提醒一次</a-radio-button>
          <a-radio-button value="daily">每天</a-radio-button>
          <a-radio-button value="weekly">每周</a-radio-button>
          <a-radio-button value="custom">每几天</a-radio-button>
        </a-radio-group>
      </a-form-item>

      <a-form-item v-if="form.repeatType === 'weekly'" label="星期几">
        <a-checkbox-group v-model:value="form.weekdays">
          <a-checkbox v-for="day in WEEKDAYS" :key="day.value" :value="day.value">
            {{ day.label }}
          </a-checkbox>
        </a-checkbox-group>
      </a-form-item>

      <a-form-item v-if="form.repeatType === 'custom'" label="间隔天数">
        <a-input-number v-model:value="form.interval" :min="1" :max="365" size="large" style="width: 160px" />
        <span class="unit-hint">天</span>
      </a-form-item>

      <a-form-item v-if="form.repeatType !== 'none'" label="结束日期（可留空，表示一直重复）">
        <a-date-picker v-model:value="form.until" format="YYYY-MM-DD" size="large" style="width: 100%" />
      </a-form-item>

      <a-form-item label="分类">
        <a-select v-model:value="form.category" size="large">
          <a-select-option v-for="item in CATEGORIES" :key="item" :value="item">
            {{ item === 'other' ? '其他' : item }}
          </a-select-option>
        </a-select>
      </a-form-item>

      <a-form-item label="备注（可留空）">
        <a-textarea v-model:value="form.content" :rows="2" placeholder="例如：饭后一片，温水送服" />
      </a-form-item>
    </a-form>

    <a-alert v-if="errorMessage" type="error" :message="errorMessage" show-icon />
  </a-modal>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import dayjs from 'dayjs'

import { reminderApi } from '@/apis/reminder_api'

const props = defineProps({
  open: { type: Boolean, default: false },
  /** 编辑时传入现有提醒，新建时为 null */
  reminder: { type: Object, default: null },
  /** 被提醒的老人 uid，留空表示给自己建 */
  targetUid: { type: String, default: '' }
})

const emit = defineEmits(['update:open', 'saved'])

const CATEGORIES = ['用药', '复诊', '饮食', '活动', 'other']
const WEEKDAYS = [
  { value: 1, label: '周一' },
  { value: 2, label: '周二' },
  { value: 3, label: '周三' },
  { value: 4, label: '周四' },
  { value: 5, label: '周五' },
  { value: 6, label: '周六' },
  { value: 7, label: '周日' }
]

const form = reactive({
  title: '',
  remindAt: null,
  repeatType: 'none',
  weekdays: [],
  interval: 2,
  until: null,
  category: 'other',
  content: ''
})

const saving = ref(false)
const errorMessage = ref('')

const isEdit = computed(() => Boolean(props.reminder && props.reminder.id))

watch(
  () => props.open,
  (visible) => {
    if (!visible) return
    saving.value = false
    errorMessage.value = ''

    const source = props.reminder
    if (source) {
      form.title = source.title || ''
      form.remindAt = source.remind_at ? dayjs(source.remind_at) : dayjs()
      form.category = source.category || 'other'
      form.content = source.content || ''
      const rule = source.repeat_rule || { type: 'none' }
      form.repeatType = rule.type || 'none'
      form.weekdays = rule.weekdays || []
      form.interval = rule.interval || 2
      form.until = rule.until ? dayjs(rule.until) : null
    } else {
      form.title = ''
      form.remindAt = dayjs().add(1, 'hour').startOf('hour')
      form.category = 'other'
      form.content = ''
      form.repeatType = 'none'
      form.weekdays = []
      form.interval = 2
      form.until = null
    }
  }
)

function buildRepeatRule() {
  if (form.repeatType === 'none') return { type: 'none' }
  const rule = { type: form.repeatType }
  if (form.repeatType === 'weekly') rule.weekdays = form.weekdays
  if (form.repeatType === 'custom') rule.interval = form.interval
  if (form.until) rule.until = form.until.format('YYYY-MM-DD')
  return rule
}

async function handleSubmit() {
  if (!form.title.trim()) {
    errorMessage.value = '请填写提醒内容'
    return
  }
  if (!form.remindAt) {
    errorMessage.value = '请选择提醒时间'
    return
  }
  if (form.repeatType === 'weekly' && form.weekdays.length === 0) {
    errorMessage.value = '每周重复请至少选择一个星期'
    return
  }

  errorMessage.value = ''
  saving.value = true
  try {
    const payload = {
      title: form.title.trim(),
      remind_at: form.remindAt.toISOString(),
      category: form.category,
      content: form.content.trim() || null,
      repeat_rule: buildRepeatRule()
    }
    if (props.targetUid) payload.target_uid = props.targetUid

    const saved = isEdit.value
      ? await reminderApi.update(props.reminder.id, payload)
      : await reminderApi.create(payload)

    emit('saved', saved)
    emit('update:open', false)
  } catch (error) {
    errorMessage.value = error.message || '保存失败'
  } finally {
    saving.value = false
  }
}

function handleCancel() {
  emit('update:open', false)
}
</script>

<style lang="less" scoped>
.unit-hint {
  margin-left: 8px;
  color: var(--gray-600, #646a73);
}

.reminder-form :deep(.ant-form-item-label > label) {
  font-size: 15px;
}
</style>
