<template>
  <div class="elder-page">
    <header class="elder-header">
      <div class="greeting-block">
        <h1 class="greeting">{{ greeting }}，{{ userStore.username || '您' }}</h1>
        <p class="today-label">{{ todayLabel }}</p>
      </div>

      <a-badge :count="familyStore.unreadMessages" :offset="[-6, 6]">
        <a-button size="large" class="family-btn" @click="goFamily">
          <Users :size="18" />
          <span>家人</span>
        </a-button>
      </a-badge>
    </header>

    <a-alert
      v-if="errorMessage"
      class="page-alert"
      type="error"
      :message="errorMessage"
      show-icon
      closable
      @close="errorMessage = ''"
    />

    <main class="elder-main">
      <div class="section-head">
        <h2 class="section-title">今天的提醒</h2>
        <span class="section-count">{{ items.length }} 条</span>
      </div>

      <a-spin :spinning="loading">
        <div v-if="!loading && items.length === 0" class="empty-state">
          <p class="empty-mark">☀</p>
          <p class="empty-text">今天没有提醒，好好休息</p>
        </div>

        <article
          v-for="item in items"
          :key="item.id"
          class="reminder-card"
          :class="`is-${item.status}`"
        >
          <div class="card-body">
            <div class="card-time">{{ formatTime(item.scheduled_at) }}</div>
            <h3 class="card-title">{{ item.title }}</h3>
            <p v-if="item.content" class="card-content">{{ item.content }}</p>

            <div class="card-meta">
              <a-tag :color="categoryColor(item.category)">{{ item.category || '提醒' }}</a-tag>
              <span v-if="item.owner_uid && item.owner_uid !== userStore.uid" class="from-family">
                家人提醒
              </span>
              <span v-if="item.repeat_rule && item.repeat_rule.type !== 'none'" class="repeat-hint">
                {{ repeatText(item.repeat_rule) }}
              </span>
            </div>
          </div>

          <div class="card-actions">
            <a-button
              v-if="needsConfirm(item.status)"
              type="primary"
              size="large"
              block
              :loading="busyId === item.id"
              @click="handleConfirm(item)"
            >
              我收到了
            </a-button>

            <div v-else-if="item.status === 'confirmed'" class="confirm-actions">
              <a-button
                type="primary"
                size="large"
                block
                :loading="busyId === item.id"
                @click="handleFinish(item, true)"
              >
                做完了
              </a-button>
              <a-button
                size="large"
                block
                :loading="busyId === item.id"
                @click="handleFinish(item, false)"
              >
                没做到
              </a-button>
            </div>

            <div v-else class="status-done">
              <span class="status-dot"></span>
              <span>{{ statusText(item.status) }}</span>
              <span v-if="item.note" class="status-note">（{{ item.note }}）</span>
            </div>
          </div>
        </article>
      </a-spin>
    </main>

    <ReminderAlertModal
      :open="alertOpen"
      :item="alertItem"
      @confirm="handleAlertConfirm"
      @later="handleAlertLater"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'
import { message } from 'ant-design-vue'
import { Users } from 'lucide-vue-next'

import { reminderApi } from '@/apis/reminder_api'
import ReminderAlertModal from '@/components/elder/ReminderAlertModal.vue'
import { playAlertChime, useAlertChime } from '@/composables/useAlertChime'
import { useTTS } from '@/composables/useTTS'
import { useFamilyStore } from '@/stores/family'
import { useUserStore } from '@/stores/user'

// 到点提醒的轮询间隔：页面停留时每分钟检查一次，确保不用刷新也能收到
const POLL_INTERVAL_MS = 60 * 1000
/** 先响铃再念，避免两个声音叠在一起 */
const SPEAK_DELAY_MS = 700

const router = useRouter()
const userStore = useUserStore()
const familyStore = useFamilyStore()
const tts = useTTS()
// 注册首次手势解锁，之后到点铃声才能真正发声
useAlertChime()
/** 延迟播报的定时器，弹窗被提前关掉时要取消 */
let speakTimer = null

const items = ref([])
const loading = ref(false)
const busyId = ref(null)
const errorMessage = ref('')

const alertOpen = ref(false)
const alertItem = ref(null)
// 本次页面停留期间已经弹过的记录，避免同一分钟反复打扰
const announcedIds = new Set()
let pollTimer = null

const greeting = computed(() => {
  const hour = dayjs().hour()
  if (hour < 6) return '夜深了'
  if (hour < 11) return '早上好'
  if (hour < 14) return '中午好'
  if (hour < 18) return '下午好'
  return '晚上好'
})

const todayLabel = computed(() => dayjs().locale('zh-cn').format('M月D日 dddd'))

const CATEGORY_COLORS = {
  用药: 'red',
  复诊: 'blue',
  饮食: 'orange',
  活动: 'green',
  other: 'default'
}

function categoryColor(category) {
  return CATEGORY_COLORS[category] || 'default'
}

function formatTime(iso) {
  return iso ? dayjs(iso).format('HH:mm') : '--:--'
}

const STATUS_TEXT = {
  pending: '待确认',
  confirmed: '已收到',
  done: '已完成',
  skipped: '未完成',
  missed: '已错过',
  delivered: '已提醒',
  seen: '已查看'
}

function statusText(status) {
  return STATUS_TEXT[status] || status
}

/**
 * 需要老人点"我收到了"的状态。
 * delivered 表示已到点但还没确认；missed 是超时未处理，仍允许老人事后确认。
 */
function needsConfirm(status) {
  return status === 'pending' || status === 'delivered' || status === 'missed'
}

function repeatText(rule) {
  if (!rule) return ''
  if (rule.type === 'daily') return '每天'
  if (rule.type === 'weekly') return `每周${(rule.weekdays || []).map((d) => '一二三四五六日'[d - 1]).join('、')}`
  if (rule.type === 'custom') return `每 ${rule.interval} 天`
  return ''
}

async function loadToday({ silent = false } = {}) {
  // 轮询时静默刷新：不闪加载圈，也不因一次网络抖动弹错误条
  if (!silent) {
    loading.value = true
    errorMessage.value = ''
  }
  try {
    const data = await reminderApi.today()
    items.value = data.items || []
  } catch (error) {
    if (!silent) errorMessage.value = error.message || '加载提醒失败，请稍后重试'
  } finally {
    if (!silent) loading.value = false
  }
}

async function handleConfirm(item) {
  busyId.value = item.id
  try {
    const updated = await reminderApi.confirm(item.id)
    Object.assign(item, updated)
  } catch (error) {
    message.error(error.message || '操作失败')
  } finally {
    busyId.value = null
  }
}

async function handleFinish(item, done) {
  busyId.value = item.id
  try {
    const updated = await reminderApi.finish(item.id, done)
    Object.assign(item, updated)
    message.success(done ? '记下了，做得好' : '已记录，明天继续加油')
  } catch (error) {
    message.error(error.message || '操作失败')
  } finally {
    busyId.value = null
  }
}

/** 老人是否开启了自动朗读（适老化设置里配置，默认关） */
function shouldReadAloud() {
  return localStorage.getItem('elderly_auto_read') === 'true'
}

/** 是否开启提醒铃声（适老化设置里配置，默认开） */
function shouldPlayChime() {
  return localStorage.getItem('elderly_alert_sound') !== 'false'
}

/** 弹最早一条"已到点但还没确认"的提醒，先响铃、再按需语音播报。 */
function showNextDueAlert() {
  if (alertOpen.value) return

  const next = items.value
    .filter((item) => item.status === 'delivered' && !announcedIds.has(item.id))
    .sort((a, b) => dayjs(a.scheduled_at).valueOf() - dayjs(b.scheduled_at).valueOf())[0]
  if (!next) return

  announcedIds.add(next.id)
  alertItem.value = next
  alertOpen.value = true

  const chimePlayed = shouldPlayChime()
  if (chimePlayed) playAlertChime()

  if (shouldReadAloud()) {
    const speak = () => tts.speak(`提醒时间到了。${next.title}`, `reminder-${next.id}`)
    if (chimePlayed) {
      speakTimer = setTimeout(speak, SPEAK_DELAY_MS)
    } else {
      speak()
    }
  }
}

function clearSpeakTimer() {
  if (speakTimer) {
    clearTimeout(speakTimer)
    speakTimer = null
  }
}

function closeAlert() {
  clearSpeakTimer()
  alertOpen.value = false
  alertItem.value = null
  tts.stop()
}

async function handleAlertConfirm() {
  const item = alertItem.value
  closeAlert()
  if (item) await handleConfirm(item)
  // 同一时刻可能有多条到点提醒，确认完继续弹下一条
  showNextDueAlert()
}

function handleAlertLater() {
  closeAlert()
}

async function refreshToday() {
  await loadToday({ silent: true })
  showNextDueAlert()
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(() => {
    // 页面在后台时不轮询，切回前台由 visibilitychange 立即补一次
    if (document.hidden) return
    refreshToday()
  }, POLL_INTERVAL_MS)
}

function handleVisibilityChange() {
  if (!document.hidden) refreshToday()
}

function goFamily() {
  // 老人端进「我的家人」（/elder/family），不是子女端的照护管理页（/family）
  // 老人在这里只能做一件事：同意或拒绝子女发来的绑定申请
  router.push('/elder/family')
}

onMounted(() => {
  refreshToday()
  familyStore.refreshUnread()
  startPolling()
  document.addEventListener('visibilitychange', handleVisibilityChange)
})

onUnmounted(() => {
  stopPolling()
  clearSpeakTimer()
  document.removeEventListener('visibilitychange', handleVisibilityChange)
  tts.stop()
})
</script>

<style lang="less" scoped>
.elder-page {
  min-height: 100%;
  padding: 24px clamp(16px, 4vw, 40px) 48px;
  background: var(--gray-25, #fafafa);
  font-size: var(--elderly-font-size, 18px);
  color: var(--gray-900, #1f2329);
}

.elder-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 24px;
}

.greeting-block {
  min-width: 0;
}

.greeting {
  margin: 0 0 6px;
  font-size: clamp(24px, 3vw, 30px);
  font-weight: 700;
  line-height: 1.3;
}

.today-label {
  margin: 0;
  font-size: 16px;
  color: var(--gray-600, #646a73);
}

.family-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 48px;
  padding: 0 20px;
  border-radius: 12px;
  font-size: 17px;
}

.page-alert {
  margin-bottom: 16px;
}

.elder-main {
  max-width: 860px;
  margin: 0 auto;
}

.section-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 16px;
}

.section-title {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
}

.section-count {
  font-size: 15px;
  color: var(--gray-500, #8f959e);
}

.empty-state {
  padding: 64px 16px;
  text-align: center;
  background: #fff;
  border-radius: 18px;
}

.empty-mark {
  margin: 0 0 12px;
  font-size: 44px;
  color: var(--main-color, #1677ff);
}

.empty-text {
  margin: 0;
  font-size: 18px;
  color: var(--gray-600, #646a73);
}

.reminder-card {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 22px 24px;
  margin-bottom: 16px;
  background: #fff;
  border-radius: 18px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.05);
  border-left: 6px solid var(--main-color, #1677ff);

  &.is-done {
    border-left-color: #52c41a;
  }

  &.is-skipped {
    border-left-color: #faad14;
  }

  &.is-confirmed {
    border-left-color: #1677ff;
  }

  &.is-delivered {
    border-left-color: #fa8c16;
  }

  &.is-missed {
    border-left-color: #ff4d4f;
  }
}

.card-time {
  font-size: 30px;
  font-weight: 700;
  line-height: 1;
  color: var(--main-color, #1677ff);
  font-variant-numeric: tabular-nums;
}

.card-title {
  margin: 10px 0 6px;
  font-size: 24px;
  font-weight: 600;
  line-height: 1.4;
}

.card-content {
  margin: 0 0 10px;
  font-size: 17px;
  line-height: 1.6;
  color: var(--gray-700, #434a54);
}

.card-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 15px;
  color: var(--gray-500, #8f959e);
}

.from-family {
  color: #eb2f96;
}

.repeat-hint {
  color: var(--gray-500, #8f959e);
}

.card-actions :deep(.ant-btn) {
  min-height: 54px;
  font-size: 19px;
  border-radius: 14px;
}

.confirm-actions {
  display: flex;
  gap: 12px;
}

.status-done {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  color: #52c41a;
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: currentColor;
}

.status-note {
  font-size: 15px;
  color: var(--gray-500, #8f959e);
}

@media (max-width: 480px) {
  .elder-page {
    padding: 16px 12px 40px;
  }

  .greeting {
    font-size: 22px;
  }

  .card-time {
    font-size: 26px;
  }

  .card-title {
    font-size: 21px;
  }

  /* 窄屏两个按钮上下排列，避免横向挤出卡片 */
  .confirm-actions {
    flex-direction: column;
  }
}
</style>
