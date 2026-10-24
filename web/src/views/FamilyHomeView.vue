<template>
  <div class="family-page">
    <header class="page-head">
      <div>
        <h1 class="page-title">家人</h1>
        <p class="page-sub">给老人安排提醒、看看今天的完成情况</p>
      </div>
      <a-button v-if="!isElderUser" type="primary" size="large" @click="openBindModal">
        <UserPlus :size="18" />
        <span class="btn-text">绑定老人</span>
      </a-button>
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

    <!-- 没有绑定任何老人时的引导 -->
    <a-empty v-if="!loadingElders && elders.length === 0" description="还没有绑定老人">
      <!-- 老人自己不该看到"绑定老人"：TA 只能等子女来申请。这里只给出解释，不提供按钮 -->
      <a-button v-if="!isElderUser" type="primary" size="large" @click="openBindModal">
        现在去绑定
      </a-button>
      <p class="empty-hint">
        {{
          isElderUser
            ? '您还没有添加家人。请家人在他们自己的账号里绑定您，您同意后就能在这里看到。'
            : '绑定后，老人会在自己的账号里看到你的申请，同意后即可开始。'
        }}
      </p>
      <a-button v-if="isElderUser" size="large" @click="router.push('/elder/family')">
        去「我的家人」看看
      </a-button>
    </a-empty>

    <template v-else>
      <!-- 紧急求助事件：未处理在前，点击横幅进来第一眼能看到 -->
      <a-alert
        v-if="emergencyEvents.length"
        class="emergency-events-alert"
        type="error"
        show-icon
      >
        <template #message>紧急求助：{{ openEmergencyCount }} 起未处理</template>
        <template #description>
          <div v-for="event in emergencyEvents" :key="event.id" class="emergency-row">
            <a-tag :color="event.status === 'open' ? 'red' : 'green'">
              {{ event.status === 'open' ? '未处理' : '已解除' }}
            </a-tag>
            <span class="emergency-elder">{{ event.elder_name || event.elder_uid }}</span>
            <span>{{ event.source === 'sos' ? 'SOS 按钮' : '聊天提到' }} · {{ emergencyCategoryLabel(event.category) }}</span>
            <span v-if="event.detail" class="emergency-quote">“{{ event.detail }}”</span>
            <span class="emergency-time">{{ formatDateTime(event.created_at) }}</span>
          </div>
        </template>
      </a-alert>

      <div class="elder-switch">
        <span class="switch-label">正在照护</span>
        <a-select
          v-model:value="currentElderUid"
          size="large"
          style="min-width: 220px"
          :options="elderOptions"
          @change="handleElderChange"
        />
      </div>

      <a-tabs v-model:activeKey="activeTab" class="family-tabs">
        <!-- 今日状态 -->
        <a-tab-pane key="status" tab="今日状态">
          <!-- 依从率只给子女看：老人看到"完成率"会把陪伴变成考核 -->
          <div v-if="!isElderUser && stats" class="stats-card">
            <div class="stats-head">
              <div class="stats-rate">
                <span class="rate-value" :class="statsRateClass">{{ statsRateText }}</span>
                <span class="rate-label">近 {{ stats.range.days }} 天完成率</span>
              </div>
              <div class="stats-counts">
                <span class="count-item"><i class="dot is-done"></i>已完成 {{ stats.summary.completed }}</span>
                <span class="count-item"><i class="dot is-failed"></i>未完成 {{ stats.summary.failed }}</span>
                <span class="count-item"><i class="dot is-pending"></i>待确认 {{ stats.summary.pending }}</span>
              </div>
            </div>

            <p v-if="stats.summary.total === 0" class="stats-empty">最近 {{ stats.range.days }} 天还没有记录</p>
            <div v-else class="stats-bars">
              <div v-for="day in stats.by_day" :key="day.date" class="bar-col" :title="dayTitle(day)">
                <div class="bar-track">
                  <div
                    class="bar-fill"
                    :class="day.total ? rateLevel(day.rate) : 'is-empty'"
                    :style="{ height: barHeight(day) }"
                  ></div>
                </div>
                <span class="bar-label">{{ dayLabel(day.date) }}</span>
              </div>
            </div>
          </div>

          <a-spin :spinning="loadingToday">
            <a-empty v-if="todayItems.length === 0" description="老人今天还没有提醒" />

            <div v-for="item in todayItems" :key="item.id" class="status-row">
              <div class="status-time">{{ formatTime(item.scheduled_at) }}</div>
              <div class="status-body">
                <div class="status-title">{{ item.title }}</div>
                <div v-if="item.content" class="status-content">{{ item.content }}</div>
                <div v-if="item.note" class="status-note">老人备注：{{ item.note }}</div>
              </div>
              <a-tag :color="statusColor(item.status)">{{ statusText(item.status) }}</a-tag>
            </div>

            <div class="status-summary">
              今天共 {{ todayItems.length }} 条，已完成
              {{ todayItems.filter((item) => item.status === 'done').length }} 条
            </div>
          </a-spin>
        </a-tab-pane>

        <!-- 提醒管理 -->
        <a-tab-pane key="manage" tab="提醒管理">
          <div class="manage-bar">
            <a-button type="primary" size="large" @click="openCreateReminder">新建提醒</a-button>
          </div>

          <a-spin :spinning="loadingReminders">
            <a-empty v-if="reminders.length === 0" description="这位老人还没有提醒" />

            <a-table
              v-else
              :data-source="reminders"
              :columns="reminderColumns"
              row-key="id"
              size="middle"
              :pagination="false"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'time'">
                  <div>{{ formatDateTime(record.remind_at) }}</div>
                  <div class="cell-sub">{{ repeatText(record.repeat_rule) }}</div>
                </template>
                <template v-else-if="column.key === 'status'">
                  <a-tag v-if="!record.enabled" color="default">已停用</a-tag>
                  <a-tag v-else color="green">启用中</a-tag>
                </template>
                <template v-else-if="column.key === 'action'">
                  <template v-if="record.is_mine">
                    <a-button type="link" @click="openEditReminder(record)">修改</a-button>
                    <a-popconfirm title="确定删除这条提醒吗？" ok-text="删除" cancel-text="取消" @confirm="handleDelete(record)">
                      <a-button type="link" danger>删除</a-button>
                    </a-popconfirm>
                  </template>
                  <span v-else class="readonly-hint">老人自己创建，仅可查看</span>
                </template>
              </template>
            </a-table>
          </a-spin>
        </a-tab-pane>

        <!-- 留言 -->
        <a-tab-pane key="message">
          <template #tab>
            <span class="tab-with-unread">
              留言
              <span v-if="familyStore.unreadMessages" class="tab-unread">
                {{ familyStore.unreadMessages }}
              </span>
            </span>
          </template>
          <a-spin :spinning="loadingMessages">
            <div ref="messageListRef" class="message-list">
              <a-empty v-if="messages.length === 0" description="还没有留言，先说句话吧" />
              <div
                v-for="msg in messages"
                :key="msg.id"
                class="message-row"
                :class="{ 'is-mine': msg.from_uid === userStore.uid }"
              >
                <div class="message-bubble">{{ msg.content }}</div>
                <div class="message-time">{{ formatDateTime(msg.created_at) }}</div>
              </div>
            </div>
          </a-spin>

          <div class="message-input">
            <a-textarea
              v-model:value="messageDraft"
              :rows="2"
              :maxlength="500"
              placeholder="给老人留句话，例如：妈，今晚我回来看您"
              @press-enter="handleSendMessage"
            />
            <a-button type="primary" size="large" :loading="sendingMessage" @click="handleSendMessage">
              发送
            </a-button>
          </div>
        </a-tab-pane>
      </a-tabs>
    </template>

    <!-- 绑定老人 -->
    <a-modal
      v-model:open="bindModalOpen"
      title="绑定老人"
      :confirm-loading="binding"
      ok-text="发送申请"
      cancel-text="取消"
      @ok="handleBind"
    >
      <a-form layout="vertical">
        <a-form-item label="老人的登录账号" required>
          <a-input v-model:value="bindForm.elderUid" size="large" placeholder="请输入老人的 UID" />
        </a-form-item>
        <a-form-item label="关系">
          <a-select v-model:value="bindForm.relation" size="large">
            <a-select-option v-for="item in RELATIONS" :key="item" :value="item">{{ item }}</a-select-option>
          </a-select>
        </a-form-item>
        <a-alert
          type="info"
          show-icon
          message="提交后需要老人在自己的账号里点“同意”，绑定才会生效。"
        />
        <a-alert v-if="bindError" class="bind-error" type="error" :message="bindError" show-icon />
      </a-form>
    </a-modal>

    <ReminderEditorModal
      v-model:open="editorOpen"
      :reminder="editingReminder"
      :target-uid="currentElderUid"
      @saved="handleReminderSaved"
    />
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import dayjs from 'dayjs'
import { message } from 'ant-design-vue'
import { UserPlus } from 'lucide-vue-next'

import { familyApi } from '@/apis/family_api'
import { reminderApi } from '@/apis/reminder_api'
import { FAMILY_UPDATED_EVENT, REMINDERS_UPDATED_EVENT } from '@/composables/useAssistantCommand'
import { emergencyCategoryLabel } from '@/utils/emergencyDetector'
import { useFamilyStore } from '@/stores/family'
import { useUserStore } from '@/stores/user'
import ReminderEditorModal from '@/components/family/ReminderEditorModal.vue'

const userStore = useUserStore()
const familyStore = useFamilyStore()
const router = useRouter()

// 老人视角进到子女端页面时，隐藏「绑定老人」入口：
// 老人只能等待子女发起申请、由自己在「我的家人」里点同意，不能主动绑定别人。
const { isElderUser } = storeToRefs(familyStore)

const RELATIONS = ['子女', '配偶', '亲属', '照护者']

const STATUS_TEXT = {
  pending: '待确认',
  confirmed: '已收到',
  done: '已完成',
  skipped: '未完成',
  missed: '已错过',
  delivered: '已提醒',
  seen: '已查看'
}

const STATUS_COLORS = {
  pending: 'default',
  confirmed: 'blue',
  done: 'green',
  skipped: 'orange',
  missed: 'red'
}

const elders = ref([])
const loadingElders = ref(false)
const currentElderUid = ref('')
const activeTab = ref('status')
const errorMessage = ref('')

// 老人侧触发的紧急求助事件（所有绑定老人，未处理在前）
const emergencyEvents = ref([])
const openEmergencyCount = computed(
  () => emergencyEvents.value.filter((event) => event.status === 'open').length
)

const todayItems = ref([])
const loadingToday = ref(false)
const stats = ref(null)

const reminders = ref([])
const loadingReminders = ref(false)

const messages = ref([])
const loadingMessages = ref(false)
const messageDraft = ref('')
const sendingMessage = ref(false)
const messageListRef = ref(null)

const bindModalOpen = ref(false)
const binding = ref(false)
const bindError = ref('')
const bindForm = reactive({ elderUid: '', relation: '子女' })

const editorOpen = ref(false)
const editingReminder = ref(null)

const elderOptions = computed(() =>
  elders.value.map((item) => ({
    value: item.elder_uid,
    label: item.elder_name ? `${item.elder_name}（${item.relation}）` : item.elder_uid
  }))
)

const reminderColumns = [
  { title: '提醒', dataIndex: 'title', key: 'title' },
  { title: '时间', key: 'time', width: 200 },
  { title: '分类', dataIndex: 'category', key: 'category', width: 100 },
  { title: '状态', key: 'status', width: 100 },
  { title: '操作', key: 'action', width: 180 }
]

function formatTime(iso) {
  return iso ? dayjs(iso).format('HH:mm') : '--:--'
}

function formatDateTime(iso) {
  return iso ? dayjs(iso).format('MM-DD HH:mm') : ''
}

function statusText(status) {
  return STATUS_TEXT[status] || status
}

function statusColor(status) {
  return STATUS_COLORS[status] || 'default'
}

function repeatText(rule) {
  if (!rule || rule.type === 'none') return '只提醒一次'
  if (rule.type === 'daily') return '每天'
  if (rule.type === 'weekly') {
    return `每周${(rule.weekdays || []).map((day) => '一二三四五六日'[day - 1]).join('、')}`
  }
  if (rule.type === 'custom') return `每 ${rule.interval} 天`
  return ''
}

async function loadElders() {
  loadingElders.value = true
  try {
    const data = await familyApi.listElders()
    elders.value = data.elders || []
    if (!currentElderUid.value && elders.value.length > 0) {
      currentElderUid.value = elders.value[0].elder_uid
    }
  } catch (error) {
    errorMessage.value = error.message || '加载老人列表失败'
  } finally {
    loadingElders.value = false
  }
}

async function loadEmergencyEvents({ silent = false } = {}) {
  try {
    const data = await familyApi.listEmergencyEvents()
    emergencyEvents.value = data.events || []
  } catch (error) {
    if (!silent) errorMessage.value = error.message || '加载紧急事件失败'
  }
}

async function loadToday({ silent = false } = {}) {
  if (!currentElderUid.value) return
  // 轮询时静默刷新：不闪加载圈，失败也不覆盖页面上的错误条
  if (!silent) loadingToday.value = true
  try {
    const data = await reminderApi.today(currentElderUid.value)
    todayItems.value = data.items || []
  } catch (error) {
    if (!silent) errorMessage.value = error.message || '加载今日状态失败'
  } finally {
    if (!silent) loadingToday.value = false
  }
}

const WEEKDAY_LABELS = '日一二三四五六'

const statsRateText = computed(() => {
  const rate = stats.value?.summary.rate
  return rate === null || rate === undefined ? '—' : `${Math.round(rate * 100)}%`
})

const statsRateClass = computed(() => rateLevel(stats.value?.summary.rate))

/** 完成率分档：≥80% 好、≥50% 一般、其余偏低。null 表示还没有可统计的记录。 */
function rateLevel(rate) {
  if (rate === null || rate === undefined) return 'is-none'
  if (rate >= 0.8) return 'is-good'
  if (rate >= 0.5) return 'is-mid'
  return 'is-low'
}

function barHeight(day) {
  if (!day.total) return '0%'
  // 有记录却一条没完成时留个可见的矮桩，否则和"当天无记录"看起来一样
  return `${Math.max(6, Math.round(day.rate * 100))}%`
}

function dayLabel(date) {
  return WEEKDAY_LABELS[dayjs(date).day()]
}

function dayTitle(day) {
  const label = dayjs(day.date).format('M月D日')
  return day.total ? `${label} 完成 ${day.completed}/${day.total}` : `${label} 无记录`
}

async function loadStats({ silent = false } = {}) {
  // 老人看自己的完成率会把陪伴变成考核，这里直接不查
  if (!currentElderUid.value || isElderUser.value) return
  try {
    stats.value = await reminderApi.stats(currentElderUid.value, 7)
  } catch (error) {
    if (!silent) errorMessage.value = error.message || '加载完成率失败'
  }
}

async function loadReminders() {
  if (!currentElderUid.value) return
  loadingReminders.value = true
  try {
    const data = await reminderApi.list(currentElderUid.value)
    reminders.value = data.reminders || []
  } catch (error) {
    errorMessage.value = error.message || '加载提醒列表失败'
  } finally {
    loadingReminders.value = false
  }
}

async function loadMessages({ silent = false } = {}) {
  if (!currentElderUid.value) return
  if (!silent) loadingMessages.value = true
  try {
    const data = await familyApi.listMessages(currentElderUid.value)
    messages.value = data.messages || []
    // 这个接口顺带把对方发来的标记为已读，侧边栏角标要跟着减，否则红点一直挂着
    if (data.marked_read) familyStore.refreshUnread()
    // 静默轮询不抢滚动位置，免得用户正在往上翻旧消息时被拽回底部
    if (!silent) scrollToLatestMessage()
  } catch (error) {
    if (!silent) errorMessage.value = error.message || '加载留言失败'
  } finally {
    if (!silent) loadingMessages.value = false
  }
}

/** 留言是流水记录，先看最新一句：打开就停在底部 */
function scrollToLatestMessage() {
  // 等一帧让气泡排版完成再算高度，否则 scrollHeight 偏小、底部最后一条会被裁掉
  nextTick(() => {
    setTimeout(() => {
      const el = messageListRef.value
      if (el) el.scrollTop = el.scrollHeight
    }, 30)
  })
}

function handleElderChange() {
  todayItems.value = []
  reminders.value = []
  messages.value = []
  stats.value = null
  refreshActiveTab()
}

function refreshActiveTab() {
  if (activeTab.value === 'status') {
    loadToday()
    loadStats()
  }
  if (activeTab.value === 'manage') loadReminders()
  if (activeTab.value === 'message') loadMessages()
}

watch(activeTab, (tab) => {
  if (!currentElderUid.value) return
  if (tab === 'status') {
    loadToday()
    loadStats()
  }
  if (tab === 'manage') loadReminders()
  if (tab === 'message') loadMessages()
})

function openBindModal() {
  bindError.value = ''
  bindForm.elderUid = ''
  bindForm.relation = '子女'
  bindModalOpen.value = true
}

async function handleBind() {
  if (!bindForm.elderUid.trim()) {
    bindError.value = '请输入老人的登录账号'
    return
  }
  binding.value = true
  bindError.value = ''
  try {
    await familyApi.createLink(bindForm.elderUid.trim(), bindForm.relation)
    message.success('申请已发送，等待老人确认')
    bindModalOpen.value = false
    await loadElders()
  } catch (error) {
    bindError.value = error.message || '发送申请失败'
  } finally {
    binding.value = false
  }
}

function openCreateReminder() {
  editingReminder.value = null
  editorOpen.value = true
}

function openEditReminder(record) {
  editingReminder.value = record
  editorOpen.value = true
}

async function handleReminderSaved() {
  message.success('已保存')
  await Promise.all([loadReminders(), loadToday()])
}

async function handleDelete(record) {
  try {
    await reminderApi.remove(record.id)
    message.success('已删除')
    await Promise.all([loadReminders(), loadToday()])
  } catch (error) {
    message.error(error.message || '删除失败')
  }
}

async function handleSendMessage() {
  const content = messageDraft.value.trim()
  if (!content || !currentElderUid.value) return
  sendingMessage.value = true
  try {
    await familyApi.sendMessage(currentElderUid.value, content)
    messageDraft.value = ''
    await loadMessages()
    scrollToLatestMessage()
  } catch (error) {
    message.error(error.message || '发送失败')
  } finally {
    sendingMessage.value = false
  }
}

// 当前 tab 每 60 秒静默刷新：老人确认提醒、发来留言都不需要子女手动刷新页面
const STATUS_POLL_INTERVAL_MS = 60 * 1000
let statusPollTimer = null

/**
 * 只刷新当前可见的 tab。
 * 今日状态会变（老人确认/标记），留言会来新的，两者都要自动更新；
 * 「提醒管理」是低频编辑页，不轮询，免得覆盖正在填的表单。
 */
function refreshActiveTabSilently() {
  if (document.hidden) return
  loadEmergencyEvents({ silent: true })
  if (activeTab.value === 'status') {
    loadToday({ silent: true })
    loadStats({ silent: true })
  }
  if (activeTab.value === 'message') loadMessages({ silent: true })
}

function stopStatusPolling() {
  if (statusPollTimer) {
    clearInterval(statusPollTimer)
    statusPollTimer = null
  }
}

function startStatusPolling() {
  stopStatusPolling()
  statusPollTimer = setInterval(refreshActiveTabSilently, STATUS_POLL_INTERVAL_MS)
}

function handleVisibilityChange() {
  if (!document.hidden) refreshActiveTabSilently()
}

onMounted(async () => {
  await loadElders()
  await loadToday()
  await loadStats()
  loadEmergencyEvents()
  startStatusPolling()
  document.addEventListener('visibilitychange', handleVisibilityChange)
  window.addEventListener(REMINDERS_UPDATED_EVENT, handleAssistantDataChanged)
  window.addEventListener(FAMILY_UPDATED_EVENT, handleAssistantDataChanged)
})

// 「问 AI」里替老人标记完成提醒或给家人发留言后，本页可能还在缓存里，靠事件刷新
function handleAssistantDataChanged() {
  loadToday({ silent: true })
  loadStats({ silent: true })
  familyStore.refreshUnread()
  if (activeTab.value === 'manage') loadReminders()
  // 不在留言 tab 时不读：读了会顺带把未读标记成已读，用户其实没看见
  if (activeTab.value === 'message') loadMessages({ silent: true })
}

onUnmounted(() => {
  stopStatusPolling()
  document.removeEventListener('visibilitychange', handleVisibilityChange)
  window.removeEventListener(REMINDERS_UPDATED_EVENT, handleAssistantDataChanged)
  window.removeEventListener(FAMILY_UPDATED_EVENT, handleAssistantDataChanged)
})
</script>

<style lang="less" scoped>
.family-page {
  padding: 24px clamp(16px, 4vw, 40px) 48px;
  background: var(--gray-25, #fafafa);
  min-height: 100%;
}

.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
}

.page-title {
  margin: 0 0 6px;
  font-size: 24px;
  font-weight: 600;
}

.page-sub {
  margin: 0;
  font-size: 14px;
  color: var(--gray-600, #646a73);
}

.btn-text {
  margin-left: 6px;
}

.page-alert {
  margin-bottom: 16px;
}

.empty-hint {
  margin-top: 16px;
  font-size: 13px;
  color: var(--gray-500, #8f959e);
}

.elder-switch {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

/* 紧急事件列表：点横幅进来后看清楚是谁、什么情况、什么时候 */
.emergency-events-alert {
  margin-bottom: 16px;
}

.emergency-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px 12px;
  padding: 4px 0;
  font-size: 14px;
}

.emergency-elder {
  font-weight: 600;
}

.emergency-quote {
  color: var(--gray-600, #646a73);
}

.emergency-time {
  margin-left: auto;
  font-size: 13px;
  color: var(--gray-500, #8f959e);
}

.switch-label {
  font-size: 15px;
  color: var(--gray-600, #646a73);
}

.family-tabs {
  background: #fff;
  padding: 8px 20px 20px;
  border-radius: 14px;
}

/* 留言 tab 上的未读数：小李点进「家人」就能看到有几句没读 */
.tab-with-unread {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.tab-unread {
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 9px;
  background: #ff4d4f;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  line-height: 18px;
  text-align: center;
}

.status-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 0;
  border-bottom: 1px solid var(--gray-100, #f0f1f3);

  &:last-of-type {
    border-bottom: none;
  }
}

.status-time {
  width: 64px;
  font-size: 18px;
  font-weight: 600;
  color: var(--main-color, #1677ff);
  font-variant-numeric: tabular-nums;
}

.status-body {
  flex: 1;
  min-width: 0;
}

.status-title {
  font-size: 16px;
  font-weight: 500;
}

.status-content,
.status-note {
  margin-top: 4px;
  font-size: 13px;
  color: var(--gray-600, #646a73);
}

.status-summary {
  margin-top: 16px;
  font-size: 14px;
  color: var(--gray-600, #646a73);
}

/* 近 7 天依从率 */
.stats-card {
  margin-bottom: 20px;
  padding: 18px 20px 12px;
  border: 1px solid var(--gray-100, #eff2f2);
  border-radius: 14px;
  background: var(--gray-25, #f8fafa);
}

.stats-head {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 24px;
  align-items: baseline;
  justify-content: space-between;
}

.stats-rate {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.rate-value {
  font-size: 32px;
  font-weight: 700;
  line-height: 1;
  font-variant-numeric: tabular-nums;
  color: var(--gray-900, #1e1f1f);

  &.is-good {
    color: #52c41a;
  }

  &.is-mid {
    color: #faad14;
  }

  &.is-low {
    color: #ff4d4f;
  }

  &.is-none {
    color: var(--gray-400, #bdbfbf);
  }
}

.rate-label {
  font-size: 14px;
  color: var(--gray-600, #697070);
}

.stats-counts {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  font-size: 13px;
  color: var(--gray-600, #697070);
}

.count-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--gray-400, #bdbfbf);

  &.is-done {
    background: #52c41a;
  }

  &.is-failed {
    background: #ff4d4f;
  }

  &.is-pending {
    background: var(--gray-300, #d0d3d3);
  }
}

.stats-empty {
  margin: 14px 0 4px;
  font-size: 14px;
  color: var(--gray-500, #8f959e);
}

.stats-bars {
  display: flex;
  gap: 10px;
  margin-top: 14px;
}

.bar-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.bar-track {
  display: flex;
  align-items: flex-end;
  width: 100%;
  max-width: 44px;
  height: 64px;
  border-radius: 6px;
  background: var(--gray-100, #eff2f2);
  overflow: hidden;
}

.bar-fill {
  width: 100%;
  border-radius: 6px 6px 0 0;
  background: var(--gray-300, #d0d3d3);
  transition: height 0.3s ease;

  &.is-good {
    background: #52c41a;
  }

  &.is-mid {
    background: #faad14;
  }

  &.is-low {
    background: #ff4d4f;
  }

  &.is-empty {
    background: transparent;
  }
}

.bar-label {
  font-size: 12px;
  color: var(--gray-500, #8f959e);
}

.manage-bar {
  margin-bottom: 16px;
}

.cell-sub {
  font-size: 12px;
  color: var(--gray-500, #8f959e);
}

.readonly-hint {
  font-size: 12px;
  color: var(--gray-400, #a8adb5);
}

.message-list {
  max-height: 420px;
  overflow-y: auto;
  padding: 8px 4px;
}

.message-row {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  margin-bottom: 14px;

  &.is-mine {
    align-items: flex-end;
  }
}

.message-bubble {
  max-width: 72%;
  padding: 10px 14px;
  border-radius: 12px;
  background: var(--gray-50, #f5f6f7);
  font-size: 15px;
  line-height: 1.6;
  word-break: break-word;
}

.is-mine .message-bubble {
  background: var(--main-color, #1677ff);
  color: #fff;
}

.message-time {
  margin-top: 4px;
  font-size: 12px;
  color: var(--gray-400, #a8adb5);
}

.message-input {
  display: flex;
  gap: 12px;
  align-items: flex-end;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--gray-100, #f0f1f3);
}

.bind-error {
  margin-top: 12px;
}
</style>
