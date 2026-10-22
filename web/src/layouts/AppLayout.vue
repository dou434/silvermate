<script setup>
import { ref, onMounted, onUnmounted, computed, provide, watch } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import {
  BarChart3,
  BellRing,
  ClipboardList,
  LibraryBig,
  Box,
  FolderKanban,
  PanelLeftClose,
  PanelLeftOpen,
  MessageCirclePlus,
  Search,
  Users
} from 'lucide-vue-next'

import { useConfigStore } from '@/stores/config'
import { useAgentStore } from '@/stores/agent'
import { useChatThreadsStore } from '@/stores/chatThreads'
import { useChatUIStore } from '@/stores/chatUI'
import { useDatabaseStore } from '@/stores/database'
import { useInfoStore } from '@/stores/info'
import { useTaskerStore } from '@/stores/tasker'
import { useUserStore } from '@/stores/user'
import { useFamilyStore } from '@/stores/family'
import { storeToRefs } from 'pinia'
import UserInfoComponent from '@/components/UserInfoComponent.vue'
import DebugComponent from '@/components/DebugComponent.vue'
import TaskCenterDrawer from '@/components/TaskCenterDrawer.vue'
import SettingsModal from '@/components/SettingsModal.vue'
import ConversationNavSection from '@/components/ConversationNavSection.vue'
import ConversationSearchModal from '@/components/ConversationSearchModal.vue'

const configStore = useConfigStore()
const agentStore = useAgentStore()
const chatThreadsStore = useChatThreadsStore()
const chatUIStore = useChatUIStore()
const databaseStore = useDatabaseStore()
const infoStore = useInfoStore()
const taskerStore = useTaskerStore()
const userStore = useUserStore()
const familyStore = useFamilyStore()
const { activeCount: activeCountRef, isDrawerOpen } = storeToRefs(taskerStore)
const { threads, currentThreadId, hasMoreThreads, isLoadingMoreThreads } =
  storeToRefs(chatThreadsStore)

// Add state for debug modal
const showDebugModal = ref(false)

// Add state for settings modal
const showSettingsModal = ref(false)
const settingsInitialTab = ref('')

const { sidebarCollapsed } = storeToRefs(chatUIStore)
const conversationSearchOpen = ref(false)

// Provide settings modal methods to child components
const openSettingsModal = (tab) => {
  settingsInitialTab.value = tab || (userStore.isAdmin ? 'base' : 'account')
  showSettingsModal.value = true
}

// Handle debug modal close
const handleDebugModalClose = () => {
  showDebugModal.value = false
}

const getRemoteConfig = async () => {
  try {
    await configStore.refreshConfig()
  } catch (error) {
    console.warn('加载系统配置失败:', error)
  }
}

const getRemoteDatabase = async () => {
  try {
    await databaseStore.loadDatabases()
  } catch (error) {
    console.warn('加载知识库列表失败:', error)
  }
}

// Fetch GitHub stars count - 银发智伴不展示 GitHub Stars
const fetchGithubStars = async () => {
  return
}

onMounted(async () => {
  // 窄屏（手机）默认收起侧边栏，把宽度让给内容区；老人端主要在手机上使用
  narrowScreenQuery = window.matchMedia('(max-width: 768px)')
  if (narrowScreenQuery.matches) {
    setSidebarCollapsed(true)
  }
  narrowScreenQuery.addEventListener('change', handleNarrowScreenChange)

  // 加载信息配置与知识库数据无依赖，可并行
  await Promise.all([infoStore.loadInfoConfig(), getRemoteDatabase()])
  // 绑定关系决定侧边栏显示「家人」还是「我的家人」，要在首屏就拿到，避免菜单闪一下再变
  familyStore.refreshLinks()
  startUnreadPolling()
  document.addEventListener('visibilitychange', handleUnreadVisibilityChange)
  await initAgentNavigation()
  await getRemoteConfig()
  // 仅管理员加载任务中心数据
  if (userStore.isAdmin) {
    taskerStore.loadTasks()
    fetchGithubStars() // Fetch GitHub stars on mount
  }
})

onUnmounted(() => {
  narrowScreenQuery?.removeEventListener('change', handleNarrowScreenChange)
  narrowScreenQuery = null
  stopUnreadPolling()
  document.removeEventListener('visibilitychange', handleUnreadVisibilityChange)
})

const route = useRoute()
const router = useRouter()

const activeTaskCount = computed(() => activeCountRef.value || 0)
const activeConversationThreadId = computed(() => {
  return route.path.startsWith('/agent') ? currentThreadId.value : null
})
const organizationName = computed(() => {
  return infoStore.organization.name || infoStore.branding.name || '银发智伴'
})

// 角色推断：后端 users 表不区分老人/子女，只能靠绑定关系判断。
// 详见 stores/family.js 里 isElderUser 的注释。
const { isElderUser, unreadMessages } = storeToRefs(familyStore)

/**
 * 未读留言轮询。
 *
 * 留言是别人异步发过来的：小李可能正停在「我的提醒」页，只在留言页刷新等于收不到。
 * 所以提到布局层每 60 秒拉一次未读数，侧边栏「家人」上的角标就是唯一入口提示。
 * 60 秒是权衡：再密是白耗请求，再疏则老人发完话子女可能半天看不到红点。
 */
const UNREAD_POLL_INTERVAL_MS = 60 * 1000
let unreadPollTimer = null

function refreshUnreadQuietly() {
  if (document.hidden) return
  familyStore.refreshUnread()
}

function startUnreadPolling() {
  stopUnreadPolling()
  familyStore.refreshUnread()
  unreadPollTimer = setInterval(refreshUnreadQuietly, UNREAD_POLL_INTERVAL_MS)
}

function stopUnreadPolling() {
  if (unreadPollTimer) {
    clearInterval(unreadPollTimer)
    unreadPollTimer = null
  }
}

// 从后台切回来时立刻补一次，不用干等下一个轮询周期
function handleUnreadVisibilityChange() {
  if (!document.hidden) familyStore.refreshUnread()
}

// 下面是导航菜单部分，添加智能体项
const mainList = computed(() => {
  const items = [
    {
      name: '我的提醒',
      path: '/elder',
      icon: BellRing,
      activeIcon: BellRing,
      action: true,
      exactActive: true
    },
    // 「家人」这一项是双侧同名的两个不同页面，必须按角色区分：
    //   老人 → /elder/family  只能同意/拒绝子女发来的绑定申请
    //   子女 → /family        绑定老人、安排提醒、查看完成情况
    // 取消角色区分会让老人看到「绑定老人」这种自己不该有的操作。
    isElderUser.value
      ? {
          name: '我的家人',
          path: '/elder/family',
          icon: Users,
          activeIcon: Users,
          badge: unreadMessages.value
        }
      : {
          name: '家人',
          path: '/family',
          icon: Users,
          activeIcon: Users,
          badge: unreadMessages.value
        },
    {
      name: '问 AI',
      path: '/agent',
      icon: MessageCirclePlus,
      activeIcon: MessageCirclePlus
    }
  ]

  // 平台管理能力只对管理员保留，普通用户界面不再暴露工作区、扩展与智能体管理
  if (userStore.isAdmin) {
    items.push({
      name: '工作区',
      path: '/workspace',
      icon: FolderKanban,
      activeIcon: FolderKanban
    })

    items.push({
      name: '智能体扩展',
      path: '/extensions',
      activePaths: ['/extensions'],
      icon: LibraryBig,
      activeIcon: LibraryBig
    })

    items.push({
      name: '智能体管理',
      path: '/model-manage',
      icon: Box,
      activeIcon: Box
    })
  }

  if (userStore.isSuperAdmin) {
    items.push({
      name: '数据总览',
      path: '/dashboard',
      icon: BarChart3,
      activeIcon: BarChart3
    })
  }

  return items
})

const primaryNavItem = computed(() => mainList.value[0] || null)
const secondaryNavItems = computed(() => mainList.value.slice(1))

const isNavItemActive = (item) => {
  const activePaths = item.activePaths || [item.path]
  if (item.exactActive) {
    return activePaths.some((path) => route.path === path)
  }
  return activePaths.some((path) => route.path === path || route.path.startsWith(`${path}/`))
}

const setSidebarCollapsed = (collapsed) => {
  sidebarCollapsed.value = collapsed
}

const toggleSidebar = () => {
  setSidebarCollapsed(!sidebarCollapsed.value)
}

// 窄屏媒体查询句柄，用于在屏幕变窄时自动收起侧边栏
let narrowScreenQuery = null

function handleNarrowScreenChange(event) {
  if (event.matches) setSidebarCollapsed(true)
}

const openConversationSearch = () => {
  conversationSearchOpen.value = true
}

const initAgentNavigation = async () => {
  try {
    if (!agentStore.isInitialized) {
      await agentStore.initialize()
    }
    await chatThreadsStore.loadThreads()
  } catch (error) {
    console.warn('加载对话导航失败:', error)
  }
}

const handleSelectChat = (threadId) => {
  if (!threadId) return
  chatThreadsStore.setCurrentThreadId(threadId)
  router.push({ name: 'AgentCompWithThreadId', params: { thread_id: threadId } })
}

const handleSearchThreadFound = (thread) => {
  chatThreadsStore.upsertThread(thread)
}

const handleSearchSelectThread = (thread) => {
  if (!thread?.id) return
  chatThreadsStore.upsertThread(thread)
  handleSelectChat(thread.id)
}

const handleCreateConversationFromSearch = () => {
  chatThreadsStore.setCurrentThreadId(null)
  router.push({ name: 'AgentComp' })
}

const handleDeleteChat = async (threadId) => {
  if (!threadId) return
  try {
    await chatThreadsStore.deleteThread(threadId)
    if (route.params.thread_id === threadId) {
      await router.replace({ name: 'AgentComp' })
    }
  } catch (error) {
    console.warn('删除对话失败:', error)
  }
}

const handleRenameChat = async ({ chatId, title }) => {
  try {
    await chatThreadsStore.updateThread(chatId, title)
  } catch (error) {
    console.warn('重命名对话失败:', error)
  }
}

const handleTogglePinChat = async (threadId) => {
  const thread = threads.value.find((item) => item.id === threadId)
  if (!thread) return
  try {
    await chatThreadsStore.updateThread(threadId, null, !thread.is_pinned)
    await chatThreadsStore.loadThreads()
    if (currentThreadId.value) {
      chatThreadsStore.setCurrentThreadId(currentThreadId.value)
    }
  } catch (error) {
    console.warn('更新置顶状态失败:', error)
  }
}

watch(
  () => [route.path, route.params.thread_id],
  () => {
    if (!route.path.startsWith('/agent')) return
    const threadId = typeof route.params.thread_id === 'string' ? route.params.thread_id : null
    chatThreadsStore.setCurrentThreadId(threadId)
  },
  { immediate: true }
)

// Provide settings modal methods to child components
provide('settingsModal', {
  openSettingsModal
})
</script>

<template>
  <div class="app-layout agent-page" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
    <div class="header">
      <div class="sidebar-brand" @click.stop>
        <router-link v-if="!sidebarCollapsed" to="/" class="brand-link">
          <img :src="infoStore.organization.logo" class="brand-avatar" />
          <span class="brand-name">{{ organizationName }}</span>
        </router-link>
        <button
          v-else
          type="button"
          class="brand-link brand-expand-button"
          aria-label="展开侧边栏"
          @click="setSidebarCollapsed(false)"
        >
          <img :src="infoStore.organization.logo" class="brand-avatar brand-avatar-image" />
          <PanelLeftOpen class="brand-expand-icon" size="20" />
        </button>
        <button
          v-if="!sidebarCollapsed"
          type="button"
          class="sidebar-toggle"
          aria-label="折叠侧边栏"
          @click="toggleSidebar"
        >
          <PanelLeftClose size="18" />
        </button>
      </div>
      <div class="nav">
        <RouterLink
          v-if="primaryNavItem"
          :to="primaryNavItem.path"
          class="nav-item"
          :class="{ active: isNavItemActive(primaryNavItem) }"
          :active-class="primaryNavItem.action ? '' : 'active'"
          @click.stop
        >
          <a-tooltip placement="right" :open="sidebarCollapsed ? undefined : false">
            <template #title>{{ primaryNavItem.name }}</template>
            <component
              class="icon"
              :is="
                isNavItemActive(primaryNavItem) ? primaryNavItem.activeIcon : primaryNavItem.icon
              "
              size="18"
            />
          </a-tooltip>
          <span class="nav-text">{{ primaryNavItem.name }}</span>
        </RouterLink>

        <button
          type="button"
          class="nav-item"
          :class="{ active: conversationSearchOpen }"
          @click.stop="openConversationSearch"
        >
          <a-tooltip placement="right" :open="sidebarCollapsed ? undefined : false">
            <template #title>搜索对话</template>
            <Search class="icon" size="18" />
          </a-tooltip>
          <span class="nav-text">搜索对话</span>
        </button>

        <RouterLink
          v-for="(item, index) in secondaryNavItems"
          :key="index"
          :to="item.path"
          v-show="!item.hidden"
          class="nav-item"
          :class="{ active: isNavItemActive(item) }"
          :active-class="item.action ? '' : 'active'"
          @click.stop
        >
          <a-tooltip placement="right" :open="sidebarCollapsed ? undefined : false">
            <template #title>{{ item.name }}</template>
            <component
              class="icon"
              :is="isNavItemActive(item) ? item.activeIcon : item.icon"
              size="18"
            />
          </a-tooltip>
          <span class="nav-text">{{ item.name }}</span>
          <span v-if="item.badge" class="nav-badge">{{ item.badge > 99 ? '99+' : item.badge }}</span>
        </RouterLink>
      </div>
      <div class="fill">
        <ConversationNavSection
          v-if="!sidebarCollapsed"
          class="sidebar-conversations"
          :current-chat-id="activeConversationThreadId"
          :chats-list="threads"
          :has-more-chats="hasMoreThreads"
          :is-loading-more="isLoadingMoreThreads"
          @select-chat="handleSelectChat"
          @delete-chat="handleDeleteChat"
          @rename-chat="handleRenameChat"
          @toggle-pin="handleTogglePinChat"
          @load-more-chats="() => chatThreadsStore.loadMoreThreads()"
        />
      </div>
      <div class="foo">
        <!-- 用户信息组件 -->
        <div class="nav-item user-info" @click.stop>
          <UserInfoComponent :show-role="!sidebarCollapsed">
            <template v-if="userStore.isAdmin" #actions>
              <a-tooltip placement="top" title="任务中心">
                <button
                  class="user-task-center"
                  :class="{ active: isDrawerOpen }"
                  type="button"
                  aria-label="任务中心"
                  @click.stop="taskerStore.openDrawer()"
                >
                  <a-badge
                    :count="activeTaskCount"
                    :overflow-count="99"
                    class="task-center-badge"
                    size="small"
                  >
                    <ClipboardList class="icon" size="16" />
                  </a-badge>
                </button>
              </a-tooltip>
            </template>
          </UserInfoComponent>
        </div>
      </div>
    </div>
    <router-view v-slot="{ Component, route }" id="app-router-view">
      <keep-alive v-if="route.meta.keepAlive !== false">
        <component :is="Component" />
      </keep-alive>
      <component :is="Component" v-else />
    </router-view>

    <ConversationSearchModal
      v-model:open="conversationSearchOpen"
      :recent-threads="threads"
      @select-thread="handleSearchSelectThread"
      @create-thread="handleCreateConversationFromSearch"
      @thread-found="handleSearchThreadFound"
    />

    <!-- Debug Modal -->
    <a-modal
      v-model:open="showDebugModal"
      title="调试面板"
      width="90%"
      :footer="null"
      @cancel="handleDebugModalClose"
      :maskClosable="true"
      :destroyOnClose="true"
      class="debug-modal"
    >
      <DebugComponent />
    </a-modal>
    <TaskCenterDrawer v-if="userStore.isAdmin" />
    <SettingsModal
      v-model:visible="showSettingsModal"
      :initial-tab="settingsInitialTab"
      @close="() => (showSettingsModal = false)"
    />
  </div>
</template>

<style lang="less" scoped>
// Less 变量定义
@sidebar-width: 230px;
@sidebar-collapsed-width: 56px;
@sidebar-padding-y: 6px;
@sidebar-padding-x: 8px;
@sidebar-padding: @sidebar-padding-y @sidebar-padding-x;
@sidebar-border-width: 1px;
@sidebar-item-height: 32px;
@sidebar-item-padding-x: 10px;
@sidebar-icon-size: 16px;
@brand-avatar-size: 28px;
@sidebar-collapsed-content-width: @sidebar-collapsed-width - (2 * @sidebar-padding-x) -
  @sidebar-border-width;
@sidebar-collapsed-icon-padding-x: (
  (@sidebar-collapsed-content-width - @sidebar-icon-size - (2 * @sidebar-border-width)) / 2
);
@sidebar-collapsed-avatar-padding-x: (
  (@sidebar-collapsed-content-width - @sidebar-item-height - (2 * @sidebar-border-width)) / 2
);
@sidebar-collapsed-brand-padding-x: ((@sidebar-collapsed-content-width - @brand-avatar-size) / 2);
@sidebar-collapsed-brand-icon-padding-x: (
  (@sidebar-collapsed-content-width - @sidebar-icon-size) / 2
);

.app-layout {
  display: flex;
  flex-direction: row;
  width: 100%;
  height: 100vh;
  min-width: var(--min-width);
}

div.header,
#app-router-view {
  height: 100%;
  max-width: 100%;
}

#app-router-view {
  flex: 1 1 auto;
  overflow-y: auto;
}

.header {
  display: flex;
  flex-direction: column;
  flex: 0 0 @sidebar-width;
  justify-content: flex-start;
  align-items: stretch;
  gap: 16px;
  background-color: var(--main-5);
  height: 100%;
  width: @sidebar-width;
  border-right: 1px solid var(--gray-100);
  padding: @sidebar-padding;
  overflow: hidden;
  user-select: none;
  transition:
    width 0.18s ease,
    flex-basis 0.18s ease;

  .nav {
    display: flex;
    flex: 0 0 auto;
    flex-direction: column;
    justify-content: flex-start;
    align-items: stretch;
    position: relative;
    gap: 4px;
  }

  .sidebar-conversations {
    height: 100%;
    min-height: 0;
    overflow: hidden;
  }

  .sidebar-brand,
  :deep(.conversation-nav-section:not(.sidebar-conversations)),
  .user-info {
    flex-shrink: 0;
  }

  .fill {
    flex: 1 1 0;
    min-height: 0;
  }

  .sidebar-brand {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: @sidebar-item-height;
    gap: 8px;
  }

  .brand-link {
    display: flex;
    flex: 1 1 auto;
    align-items: center;
    min-width: 0;
    height: @sidebar-item-height;
    color: var(--gray-900);
    text-decoration: none;
    border: 0;
    background: transparent;
    padding: 0 4px;
    cursor: pointer;
  }

  .brand-avatar {
    flex: 0 0 @brand-avatar-size;
    width: @brand-avatar-size;
    height: @brand-avatar-size;
    border-radius: 6px;
    object-fit: cover;
  }

  .brand-name {
    min-width: 0;
    margin-left: 10px;
    overflow: hidden;
    color: var(--gray-1000);
    font-size: 15px;
    font-weight: 650;
    line-height: 20px;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .sidebar-toggle {
    display: inline-flex;
    flex: 0 0 32px;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    border: 1px solid transparent;
    border-radius: 8px;
    background: transparent;
    color: var(--gray-600);
    cursor: pointer;
    transition:
      background-color 0.2s ease,
      border-color 0.2s ease,
      color 0.2s ease;

    &:hover,
    &:focus-visible {
      border-color: var(--main-50);
      background: var(--main-20);
      color: var(--main-color);
      outline: none;
    }
  }

  .nav-item {
    display: flex;
    align-items: center;
    justify-content: flex-start;
    position: relative;
    width: 100%;
    height: @sidebar-item-height;
    padding: 0 @sidebar-item-padding-x;
    border: 1px solid transparent;
    border-radius: 8px;
    background-color: transparent;
    color: var(--gray-700);
    font-size: 14px;
    font-weight: 450;
    transition:
      background-color 0.2s ease-in-out,
      border-color 0.2s ease-in-out,
      color 0.2s ease-in-out;
    margin: 0;
    text-decoration: none;
    cursor: pointer;
    outline: none;

    .icon {
      flex: 0 0 @sidebar-icon-size;
      width: @sidebar-icon-size;
      height: @sidebar-icon-size;
    }

    .nav-text {
      min-width: 0;
      max-width: 140px;
      margin-left: 8px;
      overflow: hidden;
      line-height: 20px;
      font-weight: 450;
      text-overflow: ellipsis;
      white-space: nowrap;
      transition:
        opacity 0.12s ease,
        margin-left 0.18s ease,
        max-width 0.18s ease;
    }

    // 未读留言角标：绝对定位在菜单项右侧，侧边栏收起时也不会被 nav-text 的过渡挤掉
    .nav-badge {
      position: absolute;
      top: 50%;
      right: 8px;
      transform: translateY(-50%);
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
      pointer-events: none;
    }

    & > svg:focus {
      outline: none;
    }
    & > svg:focus-visible {
      outline: none;
    }

    &.active {
      border-color: transparent;
      background-color: color-mix(in srgb, var(--main-color) 6%, var(--gray-0));
      font-weight: 600;
      color: var(--main-color);
    }

    &.primary-action {
      margin-bottom: 8px;
      border-color: var(--gray-150);
      background-color: var(--gray-0);
      color: var(--main-color);
      box-shadow: 0 3px 4px rgba(0, 10, 20, 0.02);

      &:hover {
        border-color: var(--gray-200);
        background-color: var(--gray-0);
        color: var(--main-color);
        box-shadow: 0 3px 4px rgba(0, 10, 20, 0.07);
      }
    }

    &.warning {
      color: var(--color-error-500);
    }

    &:hover {
      border-color: transparent;
      background-color: var(--main-20);
      color: var(--main-color);
    }

    &.api-docs {
      padding: 10px 12px;
    }
    &.docs {
      display: none;
    }
    &.theme-toggle-nav {
      .theme-toggle-icon {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 100%;
        height: 100%;
        cursor: pointer;
        color: var(--gray-1000);
        transition: color 0.2s ease-in-out;

        &:hover {
          color: var(--main-color);
        }
      }
    }
    &.user-info {
      margin-bottom: 8px;
      padding: 0 3px;
      overflow: hidden;

      :deep(.user-info-component) {
        width: 100%;
      }

      :deep(.user-info-dropdown) {
        width: 100%;
        height: @sidebar-item-height;
        border-radius: 8px;
        transition:
          background-color 0.2s ease,
          color 0.2s ease;
      }

      :deep(.user-info-dropdown:hover) {
        background: var(--main-20);
        color: var(--main-color);
      }
      :deep(.user-name) {
        flex: 1 1 auto;
      }

      :deep(.user-task-center) {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 28px;
        height: 28px;
        padding: 0;
        border: 1px solid transparent;
        border-radius: 6px;
        background: transparent;
        color: var(--gray-600);
        cursor: pointer;
        transition:
          background-color 0.2s ease,
          color 0.2s ease;

        &:hover,
        &.active {
          background: var(--main-30);
          color: var(--main-color);
        }

        .task-center-badge {
          display: flex;
          justify-content: center;
        }

        .icon {
          display: block;
          width: 16px;
          height: 16px;
        }
      }
    }
  }
}

.app-layout.sidebar-collapsed {
  .header {
    flex-basis: @sidebar-collapsed-width;
    width: @sidebar-collapsed-width;
    align-items: stretch;
    padding: @sidebar-padding;

    .sidebar-brand {
      justify-content: flex-start;
      width: 100%;
    }

    .brand-expand-button {
      flex: 0 0 100%;
      justify-content: flex-start;
      width: 100%;
      padding: 0;
      border-radius: 8px;

      .brand-avatar-image {
        margin-left: @sidebar-collapsed-brand-padding-x;
      }

      .brand-expand-icon {
        display: none;
        margin-left: @sidebar-collapsed-brand-icon-padding-x;
        width: @sidebar-icon-size;
        height: @sidebar-icon-size;
        color: var(--main-color);
      }

      &:hover,
      &:focus-visible {
        background: var(--main-20);
        outline: none;

        .brand-avatar-image {
          display: none;
        }

        .brand-expand-icon {
          display: block;
        }
      }
    }

    .nav {
      align-items: stretch;
      width: 100%;
    }

    .nav-item {
      justify-content: flex-start;
      width: 100%;
      padding: 0 @sidebar-collapsed-icon-padding-x;

      .nav-text {
        max-width: 0;
        margin-left: 0;
        opacity: 0;
        pointer-events: none;
      }

      &.user-info {
        padding: 0 @sidebar-collapsed-avatar-padding-x;

        :deep(.user-info-component),
        :deep(.user-info-dropdown) {
          justify-content: flex-start;
        }

        :deep(.user-info-actions) {
          display: none;
        }
      }
    }
  }
}
</style>
