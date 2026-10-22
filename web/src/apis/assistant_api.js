import { apiPost } from './base'

/**
 * 问 AI 界面的自然语言指令 API。
 *
 * 后端只做"这句话是不是一条指令"的判断与执行：是指令就直接落库并返回 reply/actions，
 * 不是就返回 handled=false，前端继续走原来的智能体对话。
 */
export const assistantApi = {
  /**
   * @param {string} text 用户原话
   * @param {string} [page] 当前路径，用于回复措辞
   * @returns {Promise<{handled: boolean, intent: string|null, reply: string, actions: Array, needs_input: boolean}>}
   */
  command: (text, page) => apiPost('/api/assistant/command', { text, page: page || null })
}

export default assistantApi
