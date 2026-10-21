/**
 * Demo 模式 Mock 数据
 *
 * 所有 API 返回的假数据都在这里定义，按 URL pattern 匹配。
 * 数据来源于真实系统截图，模拟银发智伴的主要功能展示。
 */

// ========== 系统/品牌 ==========

// 内联 SVG 用作 demo 模式 logo（避免 GitHub Pages 子目录路径问题）
const DEMO_LOGO_SVG = 'data:image/svg+xml,' + encodeURIComponent(
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect width="100" height="100" rx="22" fill="#f59e0b"/><text x="50" y="69" font-size="52" text-anchor="middle" fill="#fff" font-family="sans-serif" font-weight="bold">银</text></svg>'
)

const systemInfo = {
  success: true,
  data: {
    organization: {
      name: '银发智伴',
      logo: DEMO_LOGO_SVG,
      avatar: DEMO_LOGO_SVG
    },
    branding: {
      name: '银发智伴 SilverMate',
      title: '智慧养老 AI 助手',
      subtitle: '让科技温暖银发生活',
      subtitles: [
        '健康咨询 · 政策解读 · 护理知识 · 生活陪伴',
        '语音输入 · 语音朗读 · 大字号高对比度',
        '紧急安全机制 · SOS 一键求助',
        '养老专属知识库 · RAG 检索 · 来源可溯'
      ]
    },
    footer: {
      copyright: '© 2026 银发智伴 SilverMate',
      user_agreement_url: '',
      privacy_policy_url: ''
    }
  }
}

const systemHealth = {
  status: 'ok',
  version: '0.7.1.beta1',
  uptime: '72h 15m'
}

const publicStats = {
  agents: 4,
  conversations: 128,
  knowledge_bases: 1,
  users: 1
}

const systemConfig = {
  lite_mode: false,
  default_model: 'deepseek:deepseek-chat'
}

// ========== 用户/认证 ==========

const userInfo = {
  id: 1,
  username: 'admin',
  uid: 'admin',
  phone_number: '138****8888',
  avatar: '/silver-guardian-v2/demo/avatar.jpg',
  role: 'superadmin',
  department_id: 1,
  department_name: '管理部'
}

const loginResponse = {
  access_token: 'demo-token-xxxxx',
  token_type: 'bearer',
  user_id: 1,
  username: 'admin',
  uid: 'admin',
  phone_number: '138****8888',
  avatar: '',
  role: 'superadmin',
  department_id: 1,
  department_name: '管理部'
}

// ========== 智能体 ==========

const agents = {
  agents: [
    {
      agent_id: 'default-chatbot',
      id: 'default-chatbot',
      slug: 'default-chatbot',
      name: '银发健康顾问',
      description: '面向老年人的健康咨询助手，提供慢性病管理、用药指导、健康生活方式建议',
      is_builtin: true,
      is_subagent: false,
      config_json: {
        context: {
          model: 'deepseek:deepseek-chat',
          system_prompt: '你是银发智伴健康顾问，专门为老年人提供健康咨询服务。',
          temperature: 0.7,
          knowledges: ['银发智伴知识库'],
          skills: ['elderly-assessment', 'care-plan-generator', 'knowledge-base']
        }
      },
      configurable_items: {
        model: {
          type: 'string',
          kind: 'model_select',
          label: '模型',
          default: 'deepseek:deepseek-chat',
          options: [
            { label: 'DeepSeek Chat', value: 'deepseek:deepseek-chat' }
          ]
        },
        temperature: {
          type: 'float',
          label: '温度',
          default: 0.7,
          min: 0,
          max: 2
        },
        knowledges: {
          type: 'list',
          kind: 'knowledge_select',
          label: '知识库',
          default: ['银发智伴知识库'],
          options: [
            { label: '银发智伴知识库', value: '银发智伴知识库' }
          ]
        },
        skills: {
          type: 'list',
          kind: 'skill_select',
          label: '技能',
          default: ['elderly-assessment', 'care-plan-generator', 'knowledge-base'],
          options: [
            { label: '老年人综合评估', value: 'elderly-assessment' },
            { label: '护理计划生成', value: 'care-plan-generator' },
            { label: '知识库检索', value: 'knowledge-base' }
          ]
        }
      }
    },
    {
      agent_id: 'elderly-policy',
      id: 'elderly-policy',
      slug: 'elderly-policy',
      name: '养老政策助手',
      description: '解读养老政策法规，帮助老人和家属了解权益保障',
      is_builtin: false,
      is_subagent: false,
      config_json: {
        context: {
          model: 'deepseek:deepseek-chat',
          system_prompt: '你是养老政策助手，专门解答养老政策相关问题。',
          temperature: 0.3,
          knowledges: ['银发智伴知识库'],
          skills: ['knowledge-base']
        }
      },
      configurable_items: {}
    },
    {
      agent_id: 'nursing-care',
      id: 'nursing-care',
      slug: 'nursing-care',
      name: '护理知识助手',
      description: '提供专业的老年人护理操作规范和日常照护指导',
      is_builtin: false,
      is_subagent: false,
      config_json: {
        context: {
          model: 'deepseek:deepseek-chat',
          system_prompt: '你是护理知识助手，为照护者提供专业的护理指导。',
          temperature: 0.5,
          knowledges: ['银发智伴知识库'],
          skills: ['knowledge-base', 'care-plan-generator']
        }
      },
      configurable_items: {}
    },
    {
      agent_id: 'companion',
      id: 'companion',
      slug: 'companion',
      name: '生活陪伴',
      description: '温馨的聊天陪伴，关注老人心理健康和情感需求',
      is_builtin: false,
      is_subagent: false,
      config_json: {
        context: {
          model: 'deepseek:deepseek-chat',
          system_prompt: '你是生活陪伴助手，温暖、耐心地陪老人聊天。',
          temperature: 0.9
        }
      },
      configurable_items: {}
    }
  ]
}

const defaultChatbot = {
  agent: agents.agents[0]
}

const agentBackends = {
  backends: [
    { id: 'chatbot', name: 'Chatbot', description: '标准对话智能体' },
    { id: 'subagent', name: 'SubAgent', description: '子智能体' }
  ]
}

// ========== 对话线程 ==========
// 后端 response_model=list[ThreadResponse]，返回裸数组
const threads = [
  {
    id: 'demo-thread-1',
    uid: 'admin',
    agent_id: 'default-chatbot',
    title: '高龄津贴怎么申请？',
    created_at: '2026-07-09T10:30:00Z',
    updated_at: '2026-07-09T10:35:00Z',
    is_pinned: false,
    metadata: {}
  },
  {
    id: 'demo-thread-2',
    uid: 'admin',
    agent_id: 'default-chatbot',
    title: '高血压患者饮食注意事项',
    created_at: '2026-07-08T14:20:00Z',
    updated_at: '2026-07-08T14:30:00Z',
    is_pinned: false,
    metadata: {}
  },
  {
    id: 'demo-thread-3',
    uid: 'admin',
    agent_id: 'default-chatbot',
    title: '老年人防诈骗指南',
    created_at: '2026-07-07T09:10:00Z',
    updated_at: '2026-07-07T09:25:00Z',
    is_pinned: true,
    metadata: {}
  },
  {
    id: 'demo-thread-4',
    uid: 'admin',
    agent_id: 'elderly-policy',
    title: '老年人权益保障法咨询',
    created_at: '2026-07-06T16:00:00Z',
    updated_at: '2026-07-06T16:15:00Z',
    is_pinned: false,
    metadata: {}
  },
  {
    id: 'demo-thread-5',
    uid: 'admin',
    agent_id: 'nursing-care',
    title: '卧床老人护理操作要点',
    created_at: '2026-07-05T11:00:00Z',
    updated_at: '2026-07-05T11:30:00Z',
    is_pinned: false,
    metadata: {}
  }
]

// 后端返回 { history: [...] }，消息用 type（human/ai）而非 role
const chatHistory = {
  history: [
    {
      id: 1,
      type: 'human',
      content: '高龄津贴怎么申请？',
      created_at: '2026-07-09T10:30:00Z',
      run_id: null,
      request_id: null,
      delivery_status: 'delivered',
      extra_metadata: {},
      message_type: null,
      image_content: null,
      feedback: null
    },
    {
      id: 2,
      type: 'ai',
      content: '## 高龄津贴申请指南\n\n根据《老年人权益保障法》相关规定，**国家鼓励地方建立八十周岁以上低收入老年人高龄津贴制度**。\n\n### 申请条件\n\n| 条件项 | 说明 |\n|---|---|\n| 年龄要求 | 通常年满 80 周岁（部分地区放宽至 70 或 75 周岁） |\n| 户籍要求 | 具有当地户籍 |\n\n### 申请材料\n\n1. 本人身份证（原件及复印件）\n2. 户口簿（原件及复印件）\n3. 近期免冠照片\n4. 本人名下银行卡\n5. 《高龄津贴申请表》\n\n### 申请流程\n\n- **线上申请**：打开当地政务服务 App，搜索"高龄津贴"按指引提交\n- **线下申请**：前往户籍所在地的社区居委会/村委会办理\n\n> 📖 以上内容引用自知识库文档《老年人权益保障法要点》第 42-43 条',
      created_at: '2026-07-09T10:30:30Z',
      run_id: 'demo-run-1',
      request_id: 'demo-req-1',
      delivery_status: 'delivered',
      extra_metadata: {},
      message_type: null,
      image_content: null,
      feedback: null,
      tool_calls: [
        {
          id: 'tc-1',
          name: 'query_kb',
          function: { name: 'query_kb' },
          args: { query_text: '高龄津贴 申请' },
          tool_call_result: { content: '检索到 2 个相关片段，来自《老年人权益保障法要点》' },
          status: 'success',
          error_message: null
        }
      ]
    },
    {
      id: 3,
      type: 'human',
      content: '那津贴标准大概是多少？',
      created_at: '2026-07-09T10:32:00Z',
      run_id: null,
      request_id: null,
      delivery_status: 'delivered',
      extra_metadata: {},
      message_type: null,
      image_content: null,
      feedback: null
    },
    {
      id: 4,
      type: 'ai',
      content: '津贴标准因地而异，一般为每人每月 **50~500 元** 不等，按年龄段递增：\n\n| 年龄段 | 参考标准（月） |\n|---|---|\n| 80~89 岁 | 100~200 元 |\n| 90~99 岁 | 200~500 元 |\n| 100 岁及以上 | 300~1000 元 |\n\n> ⚠️ 以上为通用参考标准，具体金额请咨询当地民政部门。',
      created_at: '2026-07-09T10:32:15Z',
      run_id: 'demo-run-2',
      request_id: 'demo-req-2',
      delivery_status: 'delivered',
      extra_metadata: {},
      message_type: null,
      image_content: null,
      feedback: null
    }
  ]
}

const threadHistory2 = {
  history: [
    {
      id: 10,
      type: 'human',
      content: '高血压患者饮食要注意什么？',
      created_at: '2026-07-08T14:20:00Z',
      run_id: null,
      request_id: null,
      delivery_status: 'delivered',
      extra_metadata: {},
      message_type: null,
      image_content: null,
      feedback: null
    },
    {
      id: 11,
      type: 'ai',
      content: '## 高血压患者饮食建议\n\n根据《老年慢性病日常管理指南》，高血压患者应遵循以下饮食原则：\n\n### 核心原则\n\n1. **低盐饮食** — 每日食盐摄入不超过 5g\n2. **低脂饮食** — 减少动物脂肪摄入，选用植物油\n3. **高纤维** — 多吃蔬菜水果，每日不少于 500g\n4. **适量蛋白质** — 选择鱼、禽、豆制品等优质蛋白\n\n### 推荐食物\n\n- ✅ 芹菜、菠菜、西红柿\n- ✅ 燕麦、糙米\n- ✅ 鱼类（每周 2-3 次）\n\n### 限制食物\n\n- ❌ 腌制品、腊肉\n- ❌ 动物内脏\n- ❌ 浓茶、咖啡\n\n> 📖 内容引用自知识库文档《老年慢性病日常管理指南》',
      created_at: '2026-07-08T14:20:30Z',
      run_id: 'demo-run-10',
      request_id: 'demo-req-10',
      delivery_status: 'delivered',
      extra_metadata: {},
      message_type: null,
      image_content: null,
      feedback: null
    }
  ]
}

// ========== 知识库 ==========

const knowledgeBases = {
  databases: [
    {
      kb_id: 'kb_9dhul7i5k6',
      name: '银发智伴知识库',
      description: '养老领域知识库，包含政策法规、健康管理、护理规范、防诈骗指南',
      kb_type: 'milvus',
      file_count: 4,
      status: 'active',
      created_at: '2026-06-15T10:00:00Z',
      embedding_model: 'siliconflow-cn:Pro/BAAI/bge-m3'
    }
  ]
}

const knowledgeFiles = {
  files: [
    {
      file_id: 'file_024847',
      filename: '老年人权益保障法要点.md',
      file_type: 'md',
      status: 'ready',
      file_size: 3072,
      created_at: '2026-06-15T10:05:00Z'
    },
    {
      file_id: 'file_2c44fe',
      filename: '老年慢性病日常管理指南.md',
      file_type: 'md',
      status: 'ready',
      file_size: 5120,
      created_at: '2026-06-15T10:06:00Z'
    },
    {
      file_id: 'file_c6bb21',
      filename: '老年人护理操作规范.md',
      file_type: 'md',
      status: 'ready',
      file_size: 4096,
      created_at: '2026-06-15T10:07:00Z'
    },
    {
      file_id: 'file_d86cce',
      filename: '老年人防诈骗安全指南.md',
      file_type: 'md',
      status: 'ready',
      file_size: 2560,
      created_at: '2026-06-15T10:08:00Z'
    }
  ],
  total: 4
}

const knowledgeTree = {
  tree: [
    { name: '老年人权益保障法要点.md', type: 'file', file_id: 'file_024847' },
    { name: '老年慢性病日常管理指南.md', type: 'file', file_id: 'file_2c44fe' },
    { name: '老年人护理操作规范.md', type: 'file', file_id: 'file_c6bb21' },
    { name: '老年人防诈骗安全指南.md', type: 'file', file_id: 'file_d86cce' }
  ]
}

// ========== 技能 ==========

const skills = {
  data: [
    {
      slug: 'elderly-assessment',
      name: '老年人综合评估',
      description: '基于 ADL、MMSE、跌倒风险、营养状况、情绪状态等维度，生成结构化评估报告',
      category: 'assessment',
      is_builtin: true,
      icon: 'clipboard-check'
    },
    {
      slug: 'care-plan-generator',
      name: '个性化护理计划生成',
      description: '根据老人健康状况，自动生成日常安排、饮食方案、运动方案和用药管理建议',
      category: 'care',
      is_builtin: true,
      icon: 'heart'
    },
    {
      slug: 'knowledge-base',
      name: '知识库检索',
      description: '检索、打开文档、文档内定位和查看思维导图',
      category: 'knowledge',
      is_builtin: true,
      icon: 'book-open'
    },
    {
      slug: 'deep-research',
      name: '深度研究',
      description: '并行调度子智能体调研并生成结构化报告',
      category: 'research',
      is_builtin: true,
      icon: 'search'
    },
    {
      slug: 'mysql-reporter',
      name: '数据报表',
      description: '从 MySQL 数据库生成数据报表',
      category: 'data',
      is_builtin: true,
      icon: 'database'
    },
    {
      slug: 'image-gen',
      name: '图片生成',
      description: 'AI 图片生成技能',
      category: 'media',
      is_builtin: true,
      icon: 'image'
    }
  ]
}

// ========== MCP ==========

const mcpServers = {
  data: []
}

// ========== 任务 ==========

const tasks = {
  tasks: []
}

// ========== 工具 ==========

const tools = {
  tools: [
    { name: 'list_kbs', category: 'knowledge', description: '列出用户可访问的知识库' },
    { name: 'query_kb', category: 'knowledge', description: '在知识库中检索内容' },
    { name: 'open_kb_document', category: 'knowledge', description: '打开知识库文档' },
    { name: 'find_kb_document', category: 'knowledge', description: '在文档内定位关键词' },
    { name: 'get_mindmap', category: 'knowledge', description: '获取知识库思维导图' },
    { name: 'search_file', category: 'knowledge', description: '搜索知识库文件' },
    { name: 'read_file', category: 'filesystem', description: '读取文件内容' },
    { name: 'write_file', category: 'filesystem', description: '写入文件' },
    { name: 'execute_code', category: 'code', description: '执行代码' }
  ]
}

// ========== 模型供应商 ==========

const modelProviders = {
  providers: [
    {
      id: 1,
      name: 'DeepSeek',
      provider_type: 'openai',
      base_url: 'https://api.deepseek.com',
      is_enabled: true,
      models: [
        { id: 'deepseek-chat', name: 'DeepSeek Chat', model_type: 'chat' }
      ]
    },
    {
      id: 2,
      name: 'SiliconFlow',
      provider_type: 'openai',
      base_url: 'https://api.siliconflow.cn',
      is_enabled: false,
      models: [
        { id: 'Pro/BAAI/bge-m3', name: 'BGE-M3 Embedding', model_type: 'embedding' }
      ]
    }
  ]
}

// ========== 用户配置 ==========

const userConfig = {
  theme: 'amber',
  font_size: 'large',
  auto_tts: false,
  emergency_contacts: [
    { name: '儿子', phone: '138****1234' },
    { name: '社区医生', phone: '139****5678' }
  ]
}

// ========== Workspace ==========

const workspaceTree = {
  tree: [
    { name: '知识库文档', type: 'dir' },
    { name: '护理记录', type: 'dir' },
    { name: '评估报告', type: 'dir' }
  ]
}

// ========== 创建新对话 ==========

function createThread(agentId, title) {
  const threadId = 'demo-thread-' + Date.now()
  return {
    id: threadId,
    uid: 'admin',
    agent_id: agentId,
    title: title || '新的对话',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    is_pinned: false,
    metadata: {}
  }
}

// ========== 创建 Run（模拟对话） ==========

function createRunResponse(data) {
  const runId = 'demo-run-' + Date.now()
  return {
    run_id: runId,
    thread_id: data.thread_id,
    status: 'completed',
    query: data.query
  }
}

// 静态演示水印：放在 AI 回复最前面，让用户一眼识别这是预设示例
const DEMO_WATERMARK =
  '<div class="demo-watermark"><span class="demo-watermark-tag">静态演示</span>' +
  '<span class="demo-watermark-text">以下为预设示例回复，非真实 AI 生成。完整功能请在本地部署后体验。</span></div>\n\n'

// 模拟 AI 回复内容
const mockReplies = [
  '根据《老年人权益保障法》相关规定，老年人享有以下权益：\n\n1. **赡养义务** — 子女应履行经济供养、生活照料和精神慰藉的义务\n2. **医疗保障** — 享受基本医疗保险待遇\n3. **高龄津贴** — 80 周岁以上低收入老人可申请高龄津贴\n4. **社会优待** — 乘坐公共交通、参观文化设施享受优待\n\n> 📖 以上内容引用自知识库文档《老年人权益保障法要点》',
  '根据《老年慢性病日常管理指南》，建议如下：\n\n### 日常管理要点\n\n1. **定期监测** — 每日测量血压/血糖并记录\n2. **按时服药** — 遵医嘱，不擅自停药或加量\n3. **合理饮食** — 低盐低脂，多吃蔬果\n4. **适量运动** — 散步、太极拳等有氧运动\n5. **心理调节** — 保持乐观心态，多与人交流\n\n> 📖 内容引用自知识库文档《老年慢性病日常管理指南》',
  '根据《老年人护理操作规范》，护理时应注意：\n\n### 操作要点\n\n- **体位变换** — 每 2 小时翻身一次，预防压疮\n- **口腔护理** — 每日早晚清洁口腔\n- **皮肤护理** — 保持皮肤清洁干燥\n- **饮食护理** — 少量多餐，注意进食安全\n- **康复训练** — 根据老人身体状况制定计划\n\n> 📖 内容引用自知识库文档《老年人护理操作规范》'
]

// 未命中预设类别时的兜底回复
const mockFallbackReply =
  '### 🙋 演示数据暂未覆盖您的问题\n\n当前为 GitHub Pages 静态演示版本，仅内置了 **政策法规、慢病管理、护理操作** 三类问题的示例回复。\n\n**您可以尝试这些示例问题体验完整交互：**\n\n- 「高龄津贴怎么申请？」\n- 「高血压患者饮食要注意什么？」\n- 「卧床老人如何护理？」\n\n---\n\n💡 **想体验真实 AI 对话？** 请参照 [GitHub 仓库](https://github.com/LPK3215/silver-guardian-v2) 的 Docker 部署说明，在本地启动完整服务（含 DeepSeek 大模型 + Milvus 知识库检索）。'

function getMockReply(query) {
  // 命中具体类别才返回对应回复；未命中走兜底，不再"张冠李戴"
  if (query.includes('政策') || query.includes('权益') || query.includes('津贴')) {
    return DEMO_WATERMARK + mockReplies[0]
  }
  if (query.includes('健康') || query.includes('饮食') || query.includes('慢病') || query.includes('血压') || query.includes('血糖')) {
    return DEMO_WATERMARK + mockReplies[1]
  }
  if (query.includes('护理') || query.includes('卧床') || query.includes('翻身') || query.includes('压疮')) {
    return DEMO_WATERMARK + mockReplies[2]
  }
  return DEMO_WATERMARK + mockFallbackReply
}

// ========== Demo 动态消息存储 ==========
// 存储用户在 Demo 中实际发送的消息及对应 AI 回复，按线程 ID 组织

const demoThreadMessages = new Map()

/**
 * 向指定线程添加一条消息
 * @param {string} threadId
 * @param {{type: 'human'|'ai', content: string}} msg
 */
function addDemoMessage(threadId, msg) {
  if (!demoThreadMessages.has(threadId)) {
    demoThreadMessages.set(threadId, [])
  }
  const msgs = demoThreadMessages.get(threadId)
  const newMsg = {
    id: 9000 + msgs.length,
    type: msg.type,
    content: msg.content,
    created_at: new Date().toISOString(),
    run_id: msg.type === 'ai' ? 'demo-run-latest' : null,
    request_id: msg.type === 'ai' ? 'demo-req-latest' : null,
    delivery_status: 'delivered',
    extra_metadata: {},
    message_type: null,
    image_content: null,
    feedback: null
  }
  msgs.push(newMsg)
  return newMsg
}

/**
 * 获取指定线程的完整历史（静态 + 动态消息合并）
 * @param {string} threadId
 * @returns {{history: Array}}
 */
function getDemoHistory(threadId) {
  // 静态历史
  const staticMap = {
    'demo-thread-1': chatHistory.history,
    'demo-thread-2': threadHistory2.history
  }
  const staticMsgs = staticMap[threadId] || []
  const dynamicMsgs = demoThreadMessages.get(threadId) || []
  return { history: [...staticMsgs, ...dynamicMsgs] }
}

export { addDemoMessage, getDemoHistory, getMockReply }

// ========== 导出路由表 ==========

export const mockRoutes = {
  // 系统
  'GET /api/system/health': () => systemHealth,
  'GET /api/system/info': () => systemInfo,
  'GET /api/system/public-stats': () => publicStats,
  'GET /api/system/config': () => systemConfig,
  'GET /api/system/model-providers': () => modelProviders,
  'GET /api/system/model-providers/models/v2': () => ({ models: [{ id: 'deepseek-chat', name: 'DeepSeek Chat', model_type: 'chat' }] }),
  'GET /api/system/mcp-servers': () => mcpServers,
  'GET /api/system/tools': () => tools,
  'GET /api/system/tools/options': () => ({ options: tools.tools }),

  // 认证
  'GET /api/auth/me': () => userInfo,
  'GET /api/auth/check-first-run': () => ({ first_run: false }),
  'GET /api/auth/oidc/config': () => ({ enabled: false }),
  'GET /api/auth/users/access-options': () => ({ data: [] }),

  // 智能体
  'GET /api/agent': () => agents,
  'GET /api/agent/default-chatbot': () => defaultChatbot,
  'GET /api/agent/backends': () => agentBackends,

  // 对话线程
  'GET /api/chat/threads': () => threads,
  'POST /api/chat/thread': (data) => createThread(data.agent_id, data.title),
  'PUT /api/chat/thread/:threadId': (data) => ({ success: true }),
  'DELETE /api/chat/thread/:threadId': () => ({ success: true }),

  // 历史消息
  'GET /api/chat/thread/demo-thread-1/history': () => chatHistory,
  'GET /api/chat/thread/demo-thread-2/history': () => threadHistory2,
  'GET /api/chat/thread/:threadId/history': () => ({ history: [] }),
  'GET /api/chat/thread/:threadId/state': () => ({ state: {} }),
  'GET /api/chat/thread/:threadId/attachments': () => ({ attachments: [] }),
  'GET /api/chat/thread/:threadId/files': () => ({ files: [] }),

  // Agent Run
  'POST /api/agent/runs': (data) => createRunResponse(data),
  'GET /api/agent/runs/:runId': () => ({ status: 'completed' }),
  'POST /api/agent/runs/:runId/cancel': () => ({ success: true }),
  'GET /api/agent/thread/:threadId/active_run': () => ({ run: null }),

  // 知识库
  'GET /api/knowledge/databases': () => knowledgeBases,
  'GET /api/knowledge/databases/accessible': () => knowledgeBases,
  'GET /api/knowledge/databases/kb_9dhul7i5k6': () => knowledgeBases.databases[0],
  'GET /api/knowledge/databases/kb_9dhul7i5k6/query-params': () => ({
    bm25_top_k: 50, bm25_weight: 0.3, final_top_k: 10, search_mode: 'vector',
    vector_weight: 0.7, recall_top_k: 50, similarity_threshold: 0.0
  }),

  // Workspace
  'GET /api/workspace/tree': () => workspaceTree,
  'GET /api/workspace/knowledge/tree': () => knowledgeTree,

  // 技能
  'GET /api/skills/accessible': () => skills,
  'GET /api/system/skills': () => skills,

  // 任务
  'GET /api/tasks': () => tasks,

  // 用户配置
  'GET /api/user/config': () => userConfig,
  'PUT /api/user/config': () => ({ success: true }),

  // 聊天（非流式）
  'POST /api/chat/call': (data) => ({
    response: data.query.includes('标题')
      ? '银发智伴对话'
      : getMockReply(data.query || '')
  }),

  // 反馈
  'POST /api/chat/message/:messageId/feedback': () => ({ success: true }),
  'GET /api/chat/message/:messageId/feedback': () => ({ rating: null })
}
