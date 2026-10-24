/**
 * 紧急关键词检测器
 * 用于检测用户输入中的紧急求助信号，在发送前弹出安全提醒
 */

// 紧急关键词分类
const EMERGENCY_PATTERNS = {
  cardiac: {
    label: '心血管急症',
    keywords: ['胸痛', '胸闷', '心绞痛', '心脏不舒服', '心慌', '心跳加快', '心口疼'],
    advice: '您描述的症状可能是心血管急症，请立即停止活动，坐下休息。如有硝酸甘油请舌下含服。如症状持续5分钟以上不缓解，请立即拨打120。',
  },
  stroke: {
    label: '脑血管急症',
    keywords: ['半身麻木', '说话不清', '口角歪斜', '突然无力', '一侧肢体无力', '看东西模糊', '突然头晕', '站不稳'],
    advice: '您描述的症状可能是脑血管意外（中风），请立即拨打120，时间就是大脑！不要自行服药，保持安静平卧。',
  },
  fall: {
    label: '跌倒/外伤',
    keywords: ['摔倒了', '跌倒了', '摔了一跤', '站不起来', '骨折', '头摔了', '流血了'],
    advice: '请不要急于起身。先慢慢活动手指和脚趾，判断是否有骨折。如怀疑骨折或头部受伤，请不要移动，立即呼救或拨打120。',
  },
  breathing: {
    label: '呼吸困难',
    keywords: ['喘不上气', '呼吸困难', '憋气', '喘不了气', '呼吸急促', '气不够用'],
    advice: '请立即坐起，保持上身直立，解开衣领。如家里有氧气请吸氧。如症状不缓解，请立即拨打120。',
  },
  consciousness: {
    label: '意识障碍',
    keywords: ['昏迷', '意识不清', '叫不醒', '晕过去了', '人事不省', '突然倒地'],
    advice: '请立即拨打120！在等待急救人员到来前，检查呼吸和脉搏，将患者平卧，头偏向一侧防止呕吐物窒息。不要强行喂水喂药。',
  },
  bleeding: {
    label: '严重出血',
    keywords: ['大出血', '止不住血', '大量出血', '吐血', '便血'],
    advice: '请立即用干净的布压迫伤口止血。如果出血量大，请立即拨打120。保持平卧，不要喝水进食。',
  },
  psychological: {
    label: '心理危机',
    keywords: ['不想活了', '想死', '活不下去', '自杀', '了结自己'],
    advice: '您的感受我非常理解，请不要做出伤害自己的决定。请立即拨打24小时心理援助热线：400-161-9995，或联系您的家人。您不是一个人。',
  },
}

/**
 * 检测文本中是否包含紧急关键词
 * @param {string} text - 用户输入文本
 * @returns {Object|null} - { type, label, keywords, advice } 或 null
 */
export function detectEmergency(text) {
  if (!text || typeof text !== 'string') return null
  for (const [type, config] of Object.entries(EMERGENCY_PATTERNS)) {
    const matched = config.keywords.filter((kw) => text.includes(kw))
    if (matched.length > 0) {
      return { type, label: config.label, keywords: matched, advice: config.advice }
    }
  }
  return null
}

/**
 * 生成 Markdown 格式的紧急提示（供 MarkdownPreview 渲染）
 */
export function generateEmergencyMarkdown(emergency) {
  if (!emergency) return ''
  return [
    `> ⚠️ **紧急安全提醒：${emergency.label}**`,
    `>`,
    `> ${emergency.advice}`,
    `>`,
    `> 🔴 如情况紧急，请立即点击右下角 **SOS按钮** 拨打120。`,
  ].join('\n')
}

/**
 * 分类编码转中文标签（子女端的紧急事件列表用）
 * @param {string} type - 分类编码，如 cardiac / general
 */
export function emergencyCategoryLabel(type) {
  if (type === 'general') return '紧急求助'
  return EMERGENCY_PATTERNS[type]?.label || type
}

export default { detectEmergency, generateEmergencyMarkdown, emergencyCategoryLabel }
