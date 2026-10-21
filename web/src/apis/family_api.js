import { apiGet, apiPost } from './base'

/**
 * 家庭绑定与关怀留言 API
 * 权限要求：任意已登录用户；未绑定关系下的跨用户操作由后端返回 403
 */
export const familyApi = {
  /** 子女发起绑定申请，等待老人确认 */
  createLink: (elderUid, relation = '子女') =>
    apiPost('/api/family/links', { elder_uid: elderUid, relation }),

  /** 列出与我相关的绑定：as_elder 是收到的申请/已绑定的子女，as_child 是我发起的 */
  listLinks: () => apiGet('/api/family/links'),

  /** 老人确认绑定 */
  approveLink: (linkId) => apiPost(`/api/family/links/${linkId}/approve`),

  /** 解除绑定，任一方均可 */
  revokeLink: (linkId) => apiPost(`/api/family/links/${linkId}/revoke`),

  /** 子女端：已绑定的老人列表 */
  listElders: () => apiGet('/api/family/elders'),

  /** 发送关怀留言 */
  sendMessage: (toUid, content) => apiPost('/api/family/messages', { to_uid: toUid, content }),

  /** 读取与某人的留言（会顺带把对方发来的标记为已读） */
  listMessages: (withUid, limit = 50) =>
    apiGet(`/api/family/messages?with_uid=${encodeURIComponent(withUid)}&limit=${limit}`),

  /** 未读留言总数 */
  unreadCount: () => apiGet('/api/family/messages/unread-count')
}

export default familyApi
