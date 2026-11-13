import{$ as e,B as t,Ft as n,R as r,W as i,_t as a,a as o,b as s,d as c,f as l,h as u,p as d,t as f,y as p}from"./_plugin-vue_export-helper-BQgqhVXH.js";import{W as m}from"./agent-CyQN7rnR.js";import{o as h}from"./vue-router-CorCrTZD.js";import{t as g}from"./createLucideIcon-CDUQhpTg.js";import{t as _}from"./arrow-left-B9LeLVOe.js";import{t as v}from"./circle-question-mark-D2O-911k.js";import{t as y}from"./library-P-7XzK84.js";import{t as b}from"./settings-CIsM7anL.js";import{t as x}from"./info-BRYt6NMT.js";var S=g(`messages-square`,[[`path`,{d:`M16 10a2 2 0 0 1-2 2H6.828a2 2 0 0 0-1.414.586l-2.202 2.202A.71.71 0 0 1 2 14.286V4a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z`,key:`1n2ejm`}],[`path`,{d:`M20 9a2 2 0 0 1 2 2v10.286a.71.71 0 0 1-1.212.502l-2.202-2.202A2 2 0 0 0 17.172 19H10a2 2 0 0 1-2-2v-1`,key:`1qfcsi`}]]),C=g(`rocket`,[[`path`,{d:`M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5`,key:`qeys4`}],[`path`,{d:`M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09`,key:`u4xsad`}],[`path`,{d:`M9 12a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.4 22.4 0 0 1-4 2z`,key:`676m9`}],[`path`,{d:`M9 12H4s.55-3.03 2-4c1.62-1.08 5 .05 5 .05`,key:`92ym6u`}]]),w={class:`help-view`},T={class:`help-navbar`},E={class:`navbar-content`},D={class:`brand-text`},O={class:`brand-main`},k={class:`help-main`},A={class:`help-content`},j={class:`section-title`},M=[`innerHTML`],N=f({__name:`HelpView`,setup(f){let g=h(),N=x(),P=c(()=>N.branding?.name?.trim()||`银发智伴`),F=()=>g.push(`/`),I=()=>g.back(),L=[{icon:C,title:`快速开始`,content:`
      <ol>
        <li>使用管理员分配的账号密码登录系统。</li>
        <li>登录后自动进入对话页面，选择需要的智能体即可开始对话。</li>
        <li>在左侧边栏可以切换对话、查看历史记录、管理知识库等。</li>
      </ol>
    `},{icon:S,title:`智能体对话`,content:`
      <ul>
        <li><strong>新建对话</strong>：点击左侧边栏的"新建对话"按钮，选择目标智能体后开始。</li>
        <li><strong>上传附件</strong>：在对话框左侧的回形针图标可以上传文件，智能体会自动读取附件内容。</li>
        <li><strong>消息反馈</strong>：每条 AI 回复下方可以点赞或点踩，帮助优化回复质量。</li>
        <li><strong>语音朗读</strong>：点击回复消息的喇叭图标，可以使用语音朗读功能（需浏览器支持）。</li>
      </ul>
    `},{icon:y,title:`知识库管理`,content:`
      <ul>
        <li><strong>创建知识库</strong>：在"知识库"页面点击"新建"，选择向量库类型（Milvus / FAISS）后创建。</li>
        <li><strong>上传文件</strong>：进入知识库详情，点击上传按钮，支持 Markdown、PDF、Word、TXT、HTML 等格式。</li>
        <li><strong>文件状态</strong>：文件会依次经历"已上传 → 解析中 → 待入库 → 已入库"四个阶段，可在文件列表查看实时状态。</li>
        <li><strong>知识导图</strong>：知识库详情页的"知识导图"标签页可自动生成文件分类树状图，方便快速浏览知识结构。</li>
      </ul>
    `},{icon:b,title:`个人设置`,content:`
      <ul>
        <li><strong>主题切换</strong>：点击右上角头像，在下拉菜单中可切换浅色/深色模式和主题色系。</li>
        <li><strong>适老化</strong>：下拉菜单中的"适老化设置"提供大号字体、自动朗读等辅助功能。</li>
        <li><strong>账户管理</strong>：点击头像菜单中的用户名可打开账户设置，修改密码和个人信息。</li>
      </ul>
    `},{icon:v,title:`常见问题`,content:`
      <details>
        <summary>对话时提示"服务暂时不可用"？</summary>
        <p>通常是后端的 AI 模型服务未正确配置。请联系管理员在"系统设置 → 模型配置"中检查模型连接。</p>
      </details>
      <details>
        <summary>知识库文件一直显示"解析中"？</summary>
        <p>文件解析需要时间，大文件可能需要几分钟。如果长时间不变化，可能是 OCR 服务未启动，请联系管理员检查。</p>
      </details>
      <details>
        <summary>忘记登录密码？</summary>
        <p>请联系系统管理员重置密码，管理员可在"用户管理"页面操作。</p>
      </details>
    `}];return(c,f)=>{let h=m;return r(),u(`div`,w,[l(`nav`,T,[l(`div`,E,[l(`div`,{class:`brand-container`,onClick:F,style:{cursor:`pointer`}},[l(`h1`,D,[l(`span`,O,n(P.value),1),f[0]||=l(`span`,{class:`brand-separator`},null,-1),f[1]||=l(`span`,{class:`brand-sub`},`使用帮助`,-1)])]),s(h,{type:`link`,size:`small`,onClick:I},{icon:e(()=>[s(a(_),{size:16})]),default:e(()=>[f[2]||=p(` 返回 `,-1)]),_:1})])]),l(`main`,k,[l(`div`,A,[(r(),u(o,null,t(L,(e,t)=>l(`section`,{key:t,class:`help-section`},[l(`h2`,j,[(r(),d(i(e.icon),{size:22})),p(` `+n(e.title),1)]),l(`div`,{class:`section-body`,innerHTML:e.content},null,8,M)])),64))])])])}}},[[`__scopeId`,`data-v-b59aa725`]]);export{N as default};