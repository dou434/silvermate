var e=`data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%20100%20100%22%3E%3Crect%20width%3D%22100%22%20height%3D%22100%22%20rx%3D%2222%22%20fill%3D%22%23f59e0b%22%2F%3E%3Ctext%20x%3D%2250%22%20y%3D%2269%22%20font-size%3D%2252%22%20text-anchor%3D%22middle%22%20fill%3D%22%23fff%22%20font-family%3D%22sans-serif%22%20font-weight%3D%22bold%22%3E%E9%93%B6%3C%2Ftext%3E%3C%2Fsvg%3E`,t={success:!0,data:{organization:{name:`银发智伴`,logo:e,avatar:e},branding:{name:`银发智伴 SilverMate`,title:`智慧养老 AI 助手`,subtitle:`让科技温暖银发生活`,subtitles:[`健康咨询 · 政策解读 · 护理知识 · 生活陪伴`,`语音输入 · 语音朗读 · 大字号高对比度`,`紧急安全机制 · SOS 一键求助`,`养老专属知识库 · RAG 检索 · 来源可溯`]},footer:{copyright:`© 2026 银发智伴 SilverMate`,user_agreement_url:``,privacy_policy_url:``}}},n={status:`ok`,version:`0.7.1.beta1`,uptime:`72h 15m`},r={agents:4,conversations:128,knowledge_bases:1,users:1},i={lite_mode:!1,default_model:`deepseek:deepseek-chat`},a={id:1,username:`admin`,uid:`admin`,phone_number:`138****8888`,avatar:`/silver-guardian-v2/demo/avatar.jpg`,identity:`elder`,role:`superadmin`,department_id:1,department_name:`管理部`},o={agents:[{agent_id:`default-chatbot`,id:`default-chatbot`,slug:`default-chatbot`,name:`银发健康顾问`,description:`面向老年人的健康咨询助手，提供慢性病管理、用药指导、健康生活方式建议`,is_builtin:!0,is_subagent:!1,config_json:{context:{model:`deepseek:deepseek-chat`,system_prompt:`你是银发智伴健康顾问，专门为老年人提供健康咨询服务。`,temperature:.7,knowledges:[`银发智伴知识库`],skills:[`elderly-assessment`,`care-plan-generator`,`knowledge-base`]}},configurable_items:{model:{type:`string`,kind:`model_select`,label:`模型`,default:`deepseek:deepseek-chat`,options:[{label:`DeepSeek Chat`,value:`deepseek:deepseek-chat`}]},temperature:{type:`float`,label:`温度`,default:.7,min:0,max:2},knowledges:{type:`list`,kind:`knowledge_select`,label:`知识库`,default:[`银发智伴知识库`],options:[{label:`银发智伴知识库`,value:`银发智伴知识库`}]},skills:{type:`list`,kind:`skill_select`,label:`技能`,default:[`elderly-assessment`,`care-plan-generator`,`knowledge-base`],options:[{label:`老年人综合评估`,value:`elderly-assessment`},{label:`护理计划生成`,value:`care-plan-generator`},{label:`知识库检索`,value:`knowledge-base`}]}}},{agent_id:`elderly-policy`,id:`elderly-policy`,slug:`elderly-policy`,name:`养老政策助手`,description:`解读养老政策法规，帮助老人和家属了解权益保障`,is_builtin:!1,is_subagent:!1,config_json:{context:{model:`deepseek:deepseek-chat`,system_prompt:`你是养老政策助手，专门解答养老政策相关问题。`,temperature:.3,knowledges:[`银发智伴知识库`],skills:[`knowledge-base`]}},configurable_items:{}},{agent_id:`nursing-care`,id:`nursing-care`,slug:`nursing-care`,name:`护理知识助手`,description:`提供专业的老年人护理操作规范和日常照护指导`,is_builtin:!1,is_subagent:!1,config_json:{context:{model:`deepseek:deepseek-chat`,system_prompt:`你是护理知识助手，为照护者提供专业的护理指导。`,temperature:.5,knowledges:[`银发智伴知识库`],skills:[`knowledge-base`,`care-plan-generator`]}},configurable_items:{}},{agent_id:`companion`,id:`companion`,slug:`companion`,name:`生活陪伴`,description:`温馨的聊天陪伴，关注老人心理健康和情感需求`,is_builtin:!1,is_subagent:!1,config_json:{context:{model:`deepseek:deepseek-chat`,system_prompt:`你是生活陪伴助手，温暖、耐心地陪老人聊天。`,temperature:.9}},configurable_items:{}}]},s={agent:o.agents[0]},c={backends:[{id:`chatbot`,name:`Chatbot`,description:`标准对话智能体`},{id:`subagent`,name:`SubAgent`,description:`子智能体`}]},l=[{id:`demo-thread-1`,uid:`admin`,agent_id:`default-chatbot`,title:`高龄津贴怎么申请？`,created_at:`2026-07-09T10:30:00Z`,updated_at:`2026-07-09T10:35:00Z`,is_pinned:!1,metadata:{}},{id:`demo-thread-2`,uid:`admin`,agent_id:`default-chatbot`,title:`高血压患者饮食注意事项`,created_at:`2026-07-08T14:20:00Z`,updated_at:`2026-07-08T14:30:00Z`,is_pinned:!1,metadata:{}},{id:`demo-thread-3`,uid:`admin`,agent_id:`default-chatbot`,title:`老年人防诈骗指南`,created_at:`2026-07-07T09:10:00Z`,updated_at:`2026-07-07T09:25:00Z`,is_pinned:!0,metadata:{}},{id:`demo-thread-4`,uid:`admin`,agent_id:`elderly-policy`,title:`老年人权益保障法咨询`,created_at:`2026-07-06T16:00:00Z`,updated_at:`2026-07-06T16:15:00Z`,is_pinned:!1,metadata:{}},{id:`demo-thread-5`,uid:`admin`,agent_id:`nursing-care`,title:`卧床老人护理操作要点`,created_at:`2026-07-05T11:00:00Z`,updated_at:`2026-07-05T11:30:00Z`,is_pinned:!1,metadata:{}}],u={history:[{id:1,type:`human`,content:`高龄津贴怎么申请？`,created_at:`2026-07-09T10:30:00Z`,run_id:null,request_id:null,delivery_status:`delivered`,extra_metadata:{},message_type:null,image_content:null,feedback:null},{id:2,type:`ai`,content:`## 高龄津贴申请指南

根据《老年人权益保障法》相关规定，**国家鼓励地方建立八十周岁以上低收入老年人高龄津贴制度**。

### 申请条件

| 条件项 | 说明 |
|---|---|
| 年龄要求 | 通常年满 80 周岁（部分地区放宽至 70 或 75 周岁） |
| 户籍要求 | 具有当地户籍 |

### 申请材料

1. 本人身份证（原件及复印件）
2. 户口簿（原件及复印件）
3. 近期免冠照片
4. 本人名下银行卡
5. 《高龄津贴申请表》

### 申请流程

- **线上申请**：打开当地政务服务 App，搜索"高龄津贴"按指引提交
- **线下申请**：前往户籍所在地的社区居委会/村委会办理

> 📖 以上内容引用自知识库文档《老年人权益保障法要点》第 42-43 条`,created_at:`2026-07-09T10:30:30Z`,run_id:`demo-run-1`,request_id:`demo-req-1`,delivery_status:`delivered`,extra_metadata:{},message_type:null,image_content:null,feedback:null,tool_calls:[{id:`tc-1`,name:`query_kb`,function:{name:`query_kb`},args:{query_text:`高龄津贴 申请`},tool_call_result:{content:`检索到 2 个相关片段，来自《老年人权益保障法要点》`},status:`success`,error_message:null}]},{id:3,type:`human`,content:`那津贴标准大概是多少？`,created_at:`2026-07-09T10:32:00Z`,run_id:null,request_id:null,delivery_status:`delivered`,extra_metadata:{},message_type:null,image_content:null,feedback:null},{id:4,type:`ai`,content:`津贴标准因地而异，一般为每人每月 **50~500 元** 不等，按年龄段递增：

| 年龄段 | 参考标准（月） |
|---|---|
| 80~89 岁 | 100~200 元 |
| 90~99 岁 | 200~500 元 |
| 100 岁及以上 | 300~1000 元 |

> ⚠️ 以上为通用参考标准，具体金额请咨询当地民政部门。`,created_at:`2026-07-09T10:32:15Z`,run_id:`demo-run-2`,request_id:`demo-req-2`,delivery_status:`delivered`,extra_metadata:{},message_type:null,image_content:null,feedback:null}]},d={history:[{id:10,type:`human`,content:`高血压患者饮食要注意什么？`,created_at:`2026-07-08T14:20:00Z`,run_id:null,request_id:null,delivery_status:`delivered`,extra_metadata:{},message_type:null,image_content:null,feedback:null},{id:11,type:`ai`,content:`## 高血压患者饮食建议

根据《老年慢性病日常管理指南》，高血压患者应遵循以下饮食原则：

### 核心原则

1. **低盐饮食** — 每日食盐摄入不超过 5g
2. **低脂饮食** — 减少动物脂肪摄入，选用植物油
3. **高纤维** — 多吃蔬菜水果，每日不少于 500g
4. **适量蛋白质** — 选择鱼、禽、豆制品等优质蛋白

### 推荐食物

- ✅ 芹菜、菠菜、西红柿
- ✅ 燕麦、糙米
- ✅ 鱼类（每周 2-3 次）

### 限制食物

- ❌ 腌制品、腊肉
- ❌ 动物内脏
- ❌ 浓茶、咖啡

> 📖 内容引用自知识库文档《老年慢性病日常管理指南》`,created_at:`2026-07-08T14:20:30Z`,run_id:`demo-run-10`,request_id:`demo-req-10`,delivery_status:`delivered`,extra_metadata:{},message_type:null,image_content:null,feedback:null}]},f={databases:[{kb_id:`kb_9dhul7i5k6`,name:`银发智伴知识库`,description:`养老领域知识库，包含政策法规、健康管理、护理规范、防诈骗指南`,kb_type:`milvus`,file_count:4,status:`active`,created_at:`2026-06-15T10:00:00Z`,embedding_model:`siliconflow-cn:Pro/BAAI/bge-m3`}]},p={tree:[{name:`老年人权益保障法要点.md`,type:`file`,file_id:`file_024847`},{name:`老年慢性病日常管理指南.md`,type:`file`,file_id:`file_2c44fe`},{name:`老年人护理操作规范.md`,type:`file`,file_id:`file_c6bb21`},{name:`老年人防诈骗安全指南.md`,type:`file`,file_id:`file_d86cce`}]},m={data:[{slug:`elderly-assessment`,name:`老年人综合评估`,description:`基于 ADL、MMSE、跌倒风险、营养状况、情绪状态等维度，生成结构化评估报告`,category:`assessment`,is_builtin:!0,icon:`clipboard-check`},{slug:`care-plan-generator`,name:`个性化护理计划生成`,description:`根据老人健康状况，自动生成日常安排、饮食方案、运动方案和用药管理建议`,category:`care`,is_builtin:!0,icon:`heart`},{slug:`knowledge-base`,name:`知识库检索`,description:`检索、打开文档、文档内定位和查看思维导图`,category:`knowledge`,is_builtin:!0,icon:`book-open`},{slug:`deep-research`,name:`深度研究`,description:`并行调度子智能体调研并生成结构化报告`,category:`research`,is_builtin:!0,icon:`search`},{slug:`mysql-reporter`,name:`数据报表`,description:`从 MySQL 数据库生成数据报表`,category:`data`,is_builtin:!0,icon:`database`},{slug:`image-gen`,name:`图片生成`,description:`AI 图片生成技能`,category:`media`,is_builtin:!0,icon:`image`}]},h={data:[]},g={tasks:[]},_={tools:[{name:`list_kbs`,category:`knowledge`,description:`列出用户可访问的知识库`},{name:`query_kb`,category:`knowledge`,description:`在知识库中检索内容`},{name:`open_kb_document`,category:`knowledge`,description:`打开知识库文档`},{name:`find_kb_document`,category:`knowledge`,description:`在文档内定位关键词`},{name:`get_mindmap`,category:`knowledge`,description:`获取知识库思维导图`},{name:`search_file`,category:`knowledge`,description:`搜索知识库文件`},{name:`read_file`,category:`filesystem`,description:`读取文件内容`},{name:`write_file`,category:`filesystem`,description:`写入文件`},{name:`execute_code`,category:`code`,description:`执行代码`}]},v={providers:[{id:1,name:`DeepSeek`,provider_type:`openai`,base_url:`https://api.deepseek.com`,is_enabled:!0,models:[{id:`deepseek-chat`,name:`DeepSeek Chat`,model_type:`chat`}]},{id:2,name:`SiliconFlow`,provider_type:`openai`,base_url:`https://api.siliconflow.cn`,is_enabled:!1,models:[{id:`Pro/BAAI/bge-m3`,name:`BGE-M3 Embedding`,model_type:`embedding`}]}]},y={theme:`amber`,font_size:`large`,auto_tts:!1,emergency_contacts:[{name:`儿子`,phone:`138****1234`},{name:`社区医生`,phone:`139****5678`}]},b={tree:[{name:`知识库文档`,type:`dir`},{name:`护理记录`,type:`dir`},{name:`评估报告`,type:`dir`}]};function x(e,t){return{id:`demo-thread-`+Date.now(),uid:`admin`,agent_id:e,title:t||`新的对话`,created_at:new Date().toISOString(),updated_at:new Date().toISOString(),is_pinned:!1,metadata:{}}}function S(e){return{run_id:`demo-run-`+Date.now(),thread_id:e.thread_id,status:`completed`,query:e.query}}var C=`<div class="demo-watermark"><span class="demo-watermark-tag">静态演示</span><span class="demo-watermark-text">以下为预设示例回复，非真实 AI 生成。完整功能请在本地部署后体验。</span></div>

`,w=[`根据《老年人权益保障法》相关规定，老年人享有以下权益：

1. **赡养义务** — 子女应履行经济供养、生活照料和精神慰藉的义务
2. **医疗保障** — 享受基本医疗保险待遇
3. **高龄津贴** — 80 周岁以上低收入老人可申请高龄津贴
4. **社会优待** — 乘坐公共交通、参观文化设施享受优待

> 📖 以上内容引用自知识库文档《老年人权益保障法要点》`,`根据《老年慢性病日常管理指南》，建议如下：

### 日常管理要点

1. **定期监测** — 每日测量血压/血糖并记录
2. **按时服药** — 遵医嘱，不擅自停药或加量
3. **合理饮食** — 低盐低脂，多吃蔬果
4. **适量运动** — 散步、太极拳等有氧运动
5. **心理调节** — 保持乐观心态，多与人交流

> 📖 内容引用自知识库文档《老年慢性病日常管理指南》`,`根据《老年人护理操作规范》，护理时应注意：

### 操作要点

- **体位变换** — 每 2 小时翻身一次，预防压疮
- **口腔护理** — 每日早晚清洁口腔
- **皮肤护理** — 保持皮肤清洁干燥
- **饮食护理** — 少量多餐，注意进食安全
- **康复训练** — 根据老人身体状况制定计划

> 📖 内容引用自知识库文档《老年人护理操作规范》`];function T(e){return e.includes(`政策`)||e.includes(`权益`)||e.includes(`津贴`)?C+w[0]:e.includes(`健康`)||e.includes(`饮食`)||e.includes(`慢病`)||e.includes(`血压`)||e.includes(`血糖`)?C+w[1]:e.includes(`护理`)||e.includes(`卧床`)||e.includes(`翻身`)||e.includes(`压疮`)?C+w[2]:`<div class="demo-watermark"><span class="demo-watermark-tag">静态演示</span><span class="demo-watermark-text">以下为预设示例回复，非真实 AI 生成。完整功能请在本地部署后体验。</span></div>

### 🙋 演示数据暂未覆盖您的问题

当前为 GitHub Pages 静态演示版本，仅内置了 **政策法规、慢病管理、护理操作** 三类问题的示例回复。

**您可以尝试这些示例问题体验完整交互：**

- 「高龄津贴怎么申请？」
- 「高血压患者饮食要注意什么？」
- 「卧床老人如何护理？」

---

💡 **想体验真实 AI 对话？** 请参照 [GitHub 仓库](https://github.com/LPK3215/silver-guardian-v2) 的 Docker 部署说明，在本地启动完整服务（含 DeepSeek 大模型 + Milvus 知识库检索）。`}var E=new Map;function D(e,t){E.has(e)||E.set(e,[]);let n=E.get(e),r={id:9e3+n.length,type:t.type,content:t.content,created_at:new Date().toISOString(),run_id:t.type===`ai`?`demo-run-latest`:null,request_id:t.type===`ai`?`demo-req-latest`:null,delivery_status:`delivered`,extra_metadata:{},message_type:null,image_content:null,feedback:null};return n.push(r),r}function O(e){let t={"demo-thread-1":u.history,"demo-thread-2":d.history}[e]||[],n=E.get(e)||[];return{history:[...t,...n]}}var k={"GET /api/system/health":()=>n,"GET /api/system/info":()=>t,"GET /api/system/public-stats":()=>r,"GET /api/system/config":()=>i,"GET /api/system/model-providers":()=>v,"GET /api/system/model-providers/models/v2":()=>({models:[{id:`deepseek-chat`,name:`DeepSeek Chat`,model_type:`chat`}]}),"GET /api/system/mcp-servers":()=>h,"GET /api/system/tools":()=>_,"GET /api/system/tools/options":()=>({options:_.tools}),"GET /api/auth/me":()=>a,"GET /api/auth/check-first-run":()=>({first_run:!1}),"GET /api/auth/oidc/config":()=>({enabled:!1}),"GET /api/auth/users/access-options":()=>({data:[]}),"GET /api/agent":()=>o,"GET /api/agent/default-chatbot":()=>s,"GET /api/agent/backends":()=>c,"GET /api/chat/threads":()=>l,"POST /api/chat/thread":e=>x(e.agent_id,e.title),"PUT /api/chat/thread/:threadId":()=>({success:!0}),"DELETE /api/chat/thread/:threadId":()=>({success:!0}),"GET /api/chat/thread/demo-thread-1/history":()=>u,"GET /api/chat/thread/demo-thread-2/history":()=>d,"GET /api/chat/thread/:threadId/history":()=>({history:[]}),"GET /api/chat/thread/:threadId/state":()=>({state:{}}),"GET /api/chat/thread/:threadId/attachments":()=>({attachments:[]}),"GET /api/chat/thread/:threadId/files":()=>({files:[]}),"POST /api/agent/runs":e=>S(e),"GET /api/agent/runs/:runId":()=>({status:`completed`}),"POST /api/agent/runs/:runId/cancel":()=>({success:!0}),"GET /api/agent/thread/:threadId/active_run":()=>({run:null}),"GET /api/knowledge/databases":()=>f,"GET /api/knowledge/databases/accessible":()=>f,"GET /api/knowledge/databases/kb_9dhul7i5k6":()=>f.databases[0],"GET /api/knowledge/databases/kb_9dhul7i5k6/query-params":()=>({bm25_top_k:50,bm25_weight:.3,final_top_k:10,search_mode:`vector`,vector_weight:.7,recall_top_k:50,similarity_threshold:0}),"GET /api/workspace/tree":()=>b,"GET /api/workspace/knowledge/tree":()=>p,"GET /api/skills/accessible":()=>m,"GET /api/system/skills":()=>m,"GET /api/tasks":()=>g,"GET /api/user/config":()=>y,"PUT /api/user/config":()=>({success:!0}),"POST /api/chat/call":e=>({response:e.query.includes(`标题`)?`银发智伴对话`:T(e.query||``)}),"POST /api/chat/message/:messageId/feedback":()=>({success:!0}),"GET /api/chat/message/:messageId/feedback":()=>({rating:null})};function A(e,t){let n=t.split(`?`)[0],r=`${e} ${n}`;if(k[r])return{handler:k[r],params:{}};let i=Object.keys(k).filter(t=>t.startsWith(`${e} `));for(let t of i){let r=t.slice(e.length+1).split(`/`),i=n.split(`/`);if(r.length!==i.length)continue;let a={},o=!0;for(let e=0;e<r.length;e++)if(r[e].startsWith(`:`))a[r[e].slice(1)]=i[e];else if(r[e]!==i[e]){o=!1;break}if(o)return{handler:k[t],params:a}}return null}function j(e){let t=JSON.stringify(e);return{ok:!0,status:200,statusText:`OK`,headers:new Headers({"Content-Type":`application/json`}),json:()=>Promise.resolve(JSON.parse(t)),text:()=>Promise.resolve(t),blob:()=>Promise.resolve(new Blob([t],{type:`application/json`}))}}function M(){let e=window.fetch;window.fetch=async function(t,n={}){let r=typeof t==`string`?t:t?.url||``;if(!r.startsWith(`/api`)&&!r.includes(`/api/`))return e.call(window,t,n);let i=(n.method||`GET`).toUpperCase();if(i===`GET`&&r.includes(`/api/agent/runs/`)&&r.includes(`/events`)){let e=r.match(/\/api\/agent\/runs\/([^/?]+)/),t=e?e[1]:`demo-run`,n=new TextEncoder,i=`event: end
data: `+JSON.stringify({payload:{status:`completed`},run_id:t})+`

`,a=new ReadableStream({start(e){e.enqueue(n.encode(i)),e.close()}});return new Response(a,{headers:{"Content-Type":`text/event-stream`}})}let a=A(i,r);if(a){let e=null;if(n.body)try{typeof n.body==`string`?e=JSON.parse(n.body):n.body instanceof FormData&&(e={})}catch{e={}}if(await new Promise(e=>setTimeout(e,200+Math.random()*300)),i===`POST`&&r.includes(`/api/agent/runs`)&&!r.includes(`/events`)){let t=e?.query,n=e?.thread_id;t&&n&&(D(n,{type:`human`,content:t}),D(n,{type:`ai`,content:T(t)}))}let t=a.handler(e,a.params),o=r.match(/\/api\/chat\/thread\/([^/]+)\/history$/);if(i===`GET`&&o){let e=o[1];return j(O(e))}return j(t)}return console.warn(`[Demo Mode] Unmatched API: ${i} ${r}`),j({success:!0,data:null,message:`Demo mode: endpoint not mocked`})},console.log(`[Demo Mode] Mock interceptor installed`)}export{M as installMockInterceptor};