import { message } from 'ant-design-vue'
import { useRouter } from 'vue-router'
import { assistantApi } from '@/apis/assistant_api'

/**
 * 问 AI 界面的「自然语言控制」：一句话能发留言、标记提醒、跳页面。
 *
 * 分工：
 * - 判定与写库都在后端（/api/assistant/command），复用 family_service / reminder_service
 *   的权限校验，前端不拼业务请求；
 * - 前端只负责把后端给的 actions 落到界面上：toast 提示、通知其他页面刷新、路由跳转。
 *
 * 其他页面（老人端提醒列表、子女端照护页）通过监听这两个事件刷新自己，
 * 免得从 /agent 跳回去还看到旧状态。
 */
export const REMINDERS_UPDATED_EVENT = 'silvermate:reminders-updated'
export const FAMILY_UPDATED_EVENT = 'silvermate:family-updated'

/** 跳转前留一点时间，让用户看到 AI 的回复，否则点完就跳走像是没回应 */
const NAVIGATE_DELAY_MS = 700

function broadcast(eventName) {
  if (typeof window === 'undefined') return
  window.dispatchEvent(new CustomEvent(eventName))
}

export function useAssistantCommand() {
  const router = useRouter()

  /**
   * 尝试把一句话当成界面指令执行。
   * @param {string} text 用户原话
   * @returns {Promise<Object|null>} 命中返回后端结果；不是指令或接口异常返回 null（交还给智能体对话）
   */
  async function tryRun(text) {
    const content = (text || '').trim()
    if (!content) return null

    try {
      const result = await assistantApi.command(content, router.currentRoute.value?.path)
      return result?.handled ? result : null
    } catch (error) {
      // 指令接口挂了不能让用户没法聊天，静默降级走原来的智能体对话
      console.warn('[assistant-command] 解析失败，回退到智能体对话', error)
      return null
    }
  }

  /** 执行后端返回的界面动作 */
  function applyActions(actions) {
    if (!Array.isArray(actions)) return

    actions.forEach((action) => {
      if (!action || !action.type) return

      if (action.type === 'notify') {
        const fn = message[action.level] || message.info
        fn(action.message)
        return
      }

      if (action.type === 'refresh') {
        if (action.target === 'family') broadcast(FAMILY_UPDATED_EVENT)
        else broadcast(REMINDERS_UPDATED_EVENT)
        return
      }

      if (action.type === 'navigate' && action.path) {
        setTimeout(() => router.push(action.path), NAVIGATE_DELAY_MS)
      }
    })
  }

  return { tryRun, applyActions }
}

export default useAssistantCommand
