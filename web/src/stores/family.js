import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { familyApi } from '@/apis/family_api'

/**
 * 家庭相关的轻量共享状态。
 *
 * 除了未读留言角标，还负责推断「当前用户在本产品里是老人还是子女」。
 * 后端 users 表没有 role 字段区分这两种身份（role 只有 user/admin），
 * 所以只能靠绑定关系推断：
 *   - as_elder 里有记录 → 这个账号被别人当成老人照护 → 老人视角
 *   - 只有 as_child     → 这个账号在照护别人           → 子女视角
 *   - 两边都空          → 还没有任何绑定，按子女视角处理（默认能去绑定老人）
 */
export const useFamilyStore = defineStore('family', () => {
  const unreadMessages = ref(0)
  /** 名下绑定老人的未处理紧急事件数（子女端强提醒用） */
  const openEmergencies = ref(0)
  /** 原始绑定数据：{ as_elder: [], as_child: [] } */
  const links = ref({ as_elder: [], as_child: [] })
  const linksLoaded = ref(false)
  const loadingLinks = ref(false)

  /** 别人对我发起的、还没确认的申请数量（老人视角的待办） */
  const pendingAsElder = computed(
    () => links.value.as_elder.filter((item) => item.status === 'pending').length
  )

  /** 我作为老人已经建立的绑定 */
  const activeAsElder = computed(() =>
    links.value.as_elder.filter((item) => item.status === 'active')
  )

  /** 我作为子女已经建立的绑定 */
  const activeAsChild = computed(() =>
    links.value.as_child.filter((item) => item.status === 'active')
  )

  /**
   * 是否为老人视角。
   * 判定依据：有人把我当老人绑过（不论 pending 还是 active）。
   * 一旦我发起过绑定别人（as_child 非空）而没人绑我，就判定为子女视角。
   */
  const isElderUser = computed(() => links.value.as_elder.length > 0)

  async function refreshLinks() {
    loadingLinks.value = true
    try {
      const data = await familyApi.listLinks()
      links.value = {
        as_elder: data.as_elder || [],
        as_child: data.as_child || []
      }
      linksLoaded.value = true
    } catch (error) {
      // 推断角色失败不应该炸页面，静默降级为「还没加载」
      console.warn('获取绑定关系失败:', error)
    } finally {
      loadingLinks.value = false
    }
  }

  async function refreshUnread() {
    try {
      const data = await familyApi.unreadCount()
      unreadMessages.value = data.total || 0
      openEmergencies.value = data.open_emergency_count || 0
    } catch (error) {
      // 角标失败不影响主流程，静默降级
      console.warn('获取未读留言数失败:', error)
      unreadMessages.value = 0
    }
  }

  function reset() {
    unreadMessages.value = 0
    openEmergencies.value = 0
    links.value = { as_elder: [], as_child: [] }
    linksLoaded.value = false
  }

  return {
    unreadMessages,
    openEmergencies,
    links,
    linksLoaded,
    loadingLinks,
    pendingAsElder,
    activeAsElder,
    activeAsChild,
    isElderUser,
    refreshLinks,
    refreshUnread,
    reset
  }
})
