<template>
  <div class="elder-family-page">
    <header class="page-head">
      <div>
        <h1 class="page-title">我的家人</h1>
        <p class="page-sub">家人可以帮您安排提醒、看看您今天的完成情况</p>
      </div>
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

    <a-spin :spinning="loading">
      <!-- 待处理申请：老人唯一需要做的动作是"同意" -->
      <section v-if="pendingLinks.length > 0" class="section">
        <h2 class="section-title">待确认的申请</h2>
        <div v-for="link in pendingLinks" :key="link.id" class="applicant-card">
          <div class="applicant-avatar">{{ initialOf(link.child_name) }}</div>
          <div class="applicant-body">
            <div class="applicant-name">
              {{ link.child_name || link.child_uid }}
              <span class="applicant-relation">申请成为您的{{ link.relation }}</span>
            </div>
            <div class="applicant-hint">
              同意后，TA 可以帮您设置提醒，也能看到您今天的完成情况
            </div>
          </div>
          <div class="applicant-actions">
            <a-button
              type="primary"
              size="large"
              class="big-btn approve-btn"
              :loading="actingId === link.id"
              @click="handleApprove(link)"
            >
              同意
            </a-button>
            <a-button
              size="large"
              class="big-btn"
              :loading="actingId === link.id"
              @click="handleRevoke(link)"
            >
              拒绝
            </a-button>
          </div>
        </div>
      </section>

      <!-- 已加入的家人 -->
      <section class="section">
        <h2 class="section-title">已加入的家人</h2>

        <a-empty
          v-if="!loading && activeLinks.length === 0 && pendingLinks.length === 0"
          description="还没有家人加入"
        >
          <p class="empty-hint">
            请家人用他们的账号打开这个网站，输入您的登录账号
            <strong class="uid">{{ myUid || '（加载中）' }}</strong>
            发送申请，您同意后就会出现在这里。
          </p>
        </a-empty>

        <div v-else-if="activeLinks.length === 0" class="empty-line">
          还没有已加入的家人
        </div>

        <div v-for="link in activeLinks" :key="link.id" class="member-card">
          <div class="member-avatar">{{ initialOf(link.child_name) }}</div>
          <div class="member-body">
            <div class="member-name">{{ link.child_name || link.child_uid }}</div>
            <div class="member-relation">您的{{ link.relation }}</div>
          </div>
          <a-button size="large" class="big-btn" @click="handleRevoke(link)">
            解除
          </a-button>
        </div>
      </section>

      <!-- 我的账号：给家人的，方便转告 -->
      <section v-if="myUid" class="section uid-section">
        <h2 class="section-title">我的登录账号</h2>
        <div class="uid-box">
          <span class="uid">{{ myUid }}</span>
          <a-button size="large" class="big-btn" @click="copyUid">复制</a-button>
        </div>
        <p class="uid-tip">家人绑定您时，需要输入这个账号。</p>
      </section>
    </a-spin>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import { Modal } from 'ant-design-vue'

import { familyApi } from '@/apis/family_api'
import { useUserStore } from '@/stores/user'
import { useFamilyStore } from '@/stores/family'

const userStore = useUserStore()
const familyStore = useFamilyStore()

const loading = ref(false)
const actingId = ref(null)
const errorMessage = ref('')
const links = ref([])

const myUid = computed(() => userStore.uid || '')

const pendingLinks = computed(() => links.value.filter((item) => item.status === 'pending'))
const activeLinks = computed(() => links.value.filter((item) => item.status === 'active'))

function initialOf(name) {
  return (name || '家').trim().slice(0, 1)
}

async function loadLinks() {
  loading.value = true
  errorMessage.value = ''
  try {
    const data = await familyApi.listLinks()
    // 老人视角：只看别人对我发起的绑定
    links.value = data.as_elder || []
  } catch (error) {
    errorMessage.value = error.message || '加载家人列表失败'
  } finally {
    loading.value = false
  }
}

async function handleApprove(link) {
  actingId.value = link.id
  try {
    await familyApi.approveLink(link.id)
    message.success('已同意，家人现在可以帮您安排提醒了')
    await loadLinks()
  } catch (error) {
    message.error(error.message || '同意失败，请稍后再试')
  } finally {
    actingId.value = null
  }
}

function handleRevoke(link) {
  const isPending = link.status === 'pending'
  const name = link.child_name || link.child_uid
  Modal.confirm({
    title: isPending ? '确定拒绝这个申请吗？' : '确定解除绑定吗？',
    content: isPending
      ? `${name} 将无法成为您的${link.relation}，之后可以重新申请。`
      : `解除后，${name} 将不能再帮您安排提醒，也看不到您的完成情况。`,
    okText: isPending ? '拒绝' : '解除',
    okType: 'danger',
    cancelText: '取消',
    onOk: async () => {
      actingId.value = link.id
      try {
        await familyApi.revokeLink(link.id)
        message.success(isPending ? '已拒绝' : '已解除绑定')
        await Promise.all([loadLinks(), familyStore.refreshUnread()])
      } catch (error) {
        message.error(error.message || '操作失败，请稍后再试')
      } finally {
        actingId.value = null
      }
    }
  })
}

async function copyUid() {
  try {
    await navigator.clipboard.writeText(myUid.value)
    message.success('账号已复制')
  } catch {
    message.info(`您的账号是 ${myUid.value}`)
  }
}

onMounted(loadLinks)
</script>

<style lang="less" scoped>
.elder-family-page {
  padding: 24px clamp(16px, 4vw, 40px) 60px;
  max-width: 860px;
  margin: 0 auto;
}

.page-head {
  margin-bottom: 24px;
}

.page-title {
  font-size: 30px;
  font-weight: 700;
  margin: 0 0 6px;
  color: var(--text-primary, #1f2328);
}

.page-sub {
  font-size: 17px;
  color: var(--text-secondary, #6b7280);
  margin: 0;
}

.page-alert {
  margin-bottom: 20px;
}

.section {
  margin-bottom: 34px;
}

.section-title {
  font-size: 21px;
  font-weight: 600;
  margin: 0 0 14px;
  color: var(--text-primary, #1f2328);
}

/* ---- 待确认申请 ---- */
.applicant-card {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
  padding: 20px;
  border-radius: 16px;
  background: #fff7e8;
  border: 2px solid #f0b66b;
  margin-bottom: 14px;
}

.applicant-avatar,
.member-avatar {
  flex: 0 0 auto;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  font-weight: 600;
  background: #ffe2b8;
  color: #a35a00;
}

.applicant-body {
  flex: 1 1 220px;
  min-width: 0;
}

.applicant-name {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary, #1f2328);
}

.applicant-relation {
  font-size: 16px;
  font-weight: 400;
  color: #a35a00;
  margin-left: 8px;
}

.applicant-hint {
  font-size: 15px;
  color: var(--text-secondary, #6b7280);
  margin-top: 4px;
  line-height: 1.5;
}

.applicant-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

/* ---- 已加入成员 ---- */
.member-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 18px 20px;
  border-radius: 16px;
  background: var(--bg-elevated, #fff);
  border: 1px solid var(--border-color, #e5e7eb);
  margin-bottom: 12px;
}

.member-avatar {
  background: #e8f3ff;
  color: #1f6feb;
}

.member-body {
  flex: 1 1 auto;
  min-width: 0;
}

.member-name {
  font-size: 19px;
  font-weight: 600;
  color: var(--text-primary, #1f2328);
}

.member-relation {
  font-size: 15px;
  color: var(--text-secondary, #6b7280);
  margin-top: 2px;
}

/* ---- 通用 ---- */
.big-btn {
  min-height: 48px;
  min-width: 88px;
  font-size: 17px;
  border-radius: 10px;
}

.approve-btn {
  font-weight: 600;
}

.empty-hint {
  font-size: 16px;
  line-height: 1.7;
  color: var(--text-secondary, #6b7280);
  max-width: 460px;
  margin: 8px auto 0;
}

.empty-line {
  font-size: 16px;
  color: var(--text-secondary, #6b7280);
  padding: 12px 0;
}

.uid-section {
  padding-top: 10px;
  border-top: 1px dashed var(--border-color, #e5e7eb);
}

.uid-box {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}

.uid {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 20px;
  font-weight: 600;
  padding: 10px 18px;
  border-radius: 10px;
  background: var(--bg-container, #f6f8fa);
  border: 1px solid var(--border-color, #e5e7eb);
  letter-spacing: 0.5px;
}

.uid-tip {
  font-size: 15px;
  color: var(--text-secondary, #6b7280);
  margin: 10px 0 0;
}
</style>
