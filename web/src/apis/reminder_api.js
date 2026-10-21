import { apiGet, apiPost, apiPut, apiDelete } from './base'

/**
 * 提醒与执行记录 API
 * 权限要求：任意已登录用户；给他人建提醒需存在已生效的家庭绑定
 */
export const reminderApi = {
  /** 我可见的提醒：自己的、我创建的、已绑定老人的 */
  list: (targetUid) =>
    apiGet(`/api/reminders${targetUid ? `?target_uid=${encodeURIComponent(targetUid)}` : ''}`),

  /** 今日提醒（含执行状态），首次读取会补齐当天的执行记录 */
  today: (targetUid) =>
    apiGet(`/api/reminders/today${targetUid ? `?target_uid=${encodeURIComponent(targetUid)}` : ''}`),

  /** 近 N 天依从性统计（完成率、逐日明细、分类明细） */
  stats: (targetUid, days = 7) => {
    const query = new URLSearchParams({ days: String(days) })
    if (targetUid) query.set('target_uid', targetUid)
    return apiGet(`/api/reminders/stats?${query.toString()}`)
  },

  /** 创建提醒。target_uid 留空表示给自己建 */
  create: (payload) => apiPost('/api/reminders', payload),

  /** 修改提醒，仅创建者本人 */
  update: (reminderId, payload) => apiPut(`/api/reminders/${reminderId}`, payload),

  /** 删除提醒（软删除），仅创建者本人 */
  remove: (reminderId) => apiDelete(`/api/reminders/${reminderId}`),

  /** 某条提醒的历史执行记录 */
  occurrences: (reminderId) => apiGet(`/api/reminders/${reminderId}/occurrences`),

  /** 老人确认收到 */
  confirm: (occurrenceId) => apiPost(`/api/reminders/occurrences/${occurrenceId}/confirm`),

  /** 老人标记完成或未完成 */
  finish: (occurrenceId, done, note) =>
    apiPost(`/api/reminders/occurrences/${occurrenceId}/finish`, { done, note: note || null })
}

export default reminderApi
