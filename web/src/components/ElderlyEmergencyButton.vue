<template>
  <div class="elderly-emergency-wrapper">
    <!-- 紧急求助浮动按钮 -->
    <button
      class="elderly-emergency-button"
      @click="openModal"
      title="紧急求助"
    >
      <span class="elderly-emergency-icon">SOS</span>
      <span>紧急求助</span>
    </button>

    <!-- 紧急求助弹窗 -->
    <a-modal
      v-model:open="showModal"
      :width="480"
      :footer="null"
      class="elderly-emergency-modal"
    >
      <div style="text-align: center; padding: 16px 0;">
        <h2 style="margin-bottom: 16px; color: var(--color-error-500, #ff4d4f);">紧急求助</h2>
        <p style="font-size: 18px; color: #666; margin-bottom: 20px;">
          如果您遇到紧急情况，请立即拨打以下电话：
        </p>

        <div style="font-size: 36px; font-weight: bold; color: var(--color-error-500, #ff4d4f); letter-spacing: 4px;">120</div>
        <p style="font-size: 16px; color: #999; margin-bottom: 16px;">急救电话</p>

        <div style="font-size: 36px; font-weight: bold; color: var(--color-error-500, #ff4d4f); letter-spacing: 4px;">110</div>
        <p style="font-size: 16px; color: #999; margin-bottom: 16px;">报警电话</p>

        <!-- 绑定家人：来源是家庭绑定数据，留了手机号的可以直接拨打 -->
        <div v-if="familyContacts.length" class="elderly-emergency-family">
          <button
            v-for="contact in familyContacts"
            :key="contact.uid"
            type="button"
            class="elderly-emergency-contact"
            @click="callNumber(contact.phone)"
          >
            {{ contact.name }}（{{ contact.relation }}）
            <span class="elderly-emergency-contact-phone">{{ contact.phone }}</span>
          </button>
        </div>
        <p v-else style="font-size: 14px; color: #ccc; margin-bottom: 24px;">还没有绑定家人</p>

        <div style="display: flex; gap: 12px;">
          <a-button
            type="primary"
            danger
            size="large"
            style="flex: 1; min-height: 52px;"
            :loading="notifying"
            @click="notifyFamily"
          >
            通知家人
          </a-button>
          <a-button
            v-if="openEventId"
            size="large"
            style="flex: 1; min-height: 52px;"
            :loading="resolving"
            @click="resolveEvent"
          >
            我没事了
          </a-button>
          <a-button size="large" style="min-height: 52px;" @click="showModal = false">
            关闭
          </a-button>
        </div>

        <p
          v-if="feedback"
          class="elderly-emergency-feedback"
          :style="{ color: FEEDBACK_COLORS[feedback.type] }"
        >
          {{ feedback.text }}
        </p>
      </div>
    </a-modal>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { familyApi } from '@/apis/family_api'
import { useFamilyStore } from '@/stores/family'

const familyStore = useFamilyStore()

const showModal = ref(false)
const notifying = ref(false)
const resolving = ref(false)
// 最近一次「通知家人」产生的未解除事件 id；有值才显示「我没事了」
const openEventId = ref(null)
const feedback = ref(null)

const FEEDBACK_COLORS = {
  success: '#52c41a',
  info: '#1677ff',
  warning: '#faad14',
  error: '#ff4d4f'
}

// 已绑定且留了手机号的家人，作为「联系家人」的号码来源
const familyContacts = computed(() =>
  familyStore.activeAsElder
    .filter((link) => link.child_phone)
    .map((link) => ({
      uid: link.child_uid,
      name: link.child_name || link.child_uid,
      relation: link.relation || '家人',
      phone: link.child_phone
    }))
)

function openModal() {
  showModal.value = true
  if (!familyStore.linksLoaded) familyStore.refreshLinks()
}

function callNumber(number) {
  window.location.href = `tel:${number}`
}

async function notifyFamily() {
  notifying.value = true
  feedback.value = null
  try {
    const res = await familyApi.reportEmergency({ source: 'sos' })
    openEventId.value = res.event_id
    if (res.deduped) {
      feedback.value = { type: 'info', text: '10 分钟内已通知过家人，不会重复发送' }
    } else if (res.notified?.length) {
      feedback.value = { type: 'success', text: `已通知 ${res.notified.length} 位家人，请保持电话畅通` }
    } else {
      feedback.value = { type: 'warning', text: '您还没有绑定家人，未能通知。请让家人在他们的账号里绑定您' }
    }
  } catch (error) {
    feedback.value = { type: 'error', text: error.message || '通知失败，请重试' }
  } finally {
    notifying.value = false
  }
}

async function resolveEvent() {
  if (!openEventId.value) return
  resolving.value = true
  feedback.value = null
  try {
    const res = await familyApi.resolveEmergency(openEventId.value)
    openEventId.value = null
    if (res.already_resolved) {
      feedback.value = { type: 'info', text: '这起求助已经解除过了' }
    } else {
      feedback.value = { type: 'success', text: `已通知 ${res.notified.length} 位家人您没事了` }
    }
  } catch (error) {
    feedback.value = { type: 'error', text: error.message || '操作失败，请重试' }
  } finally {
    resolving.value = false
  }
}
</script>

<style>
/* 样式在 elderly-friendly.css 中定义，这里不需要 scoped */
</style>
