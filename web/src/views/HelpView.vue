<template>
  <div class="help-view">
    <nav class="help-navbar">
      <div class="navbar-content">
        <div class="brand-container" @click="goHome" style="cursor: pointer">
          <h1 class="brand-text">
            <span class="brand-main">{{ brandName }}</span>
            <span class="brand-separator"></span>
            <span class="brand-sub">使用帮助</span>
          </h1>
        </div>
        <a-button type="link" size="small" @click="goBack">
          <template #icon><ArrowLeft :size="16" /></template>
          返回
        </a-button>
      </div>
    </nav>

    <main class="help-main">
      <div class="help-content">
        <section v-for="(section, i) in sections" :key="i" class="help-section">
          <h2 class="section-title">
            <component :is="section.icon" :size="22" />
            {{ section.title }}
          </h2>
          <div class="section-body" v-html="section.content"></div>
        </section>
      </div>
    </main>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useInfoStore } from '@/stores/info'
import {
  ArrowLeft,
  Rocket,
  MessagesSquare,
  Library,
  Settings,
  CircleHelp
} from 'lucide-vue-next'

const router = useRouter()
const infoStore = useInfoStore()

const brandName = computed(() => {
  return infoStore.branding?.name?.trim() || '银发智伴'
})

const goHome = () => router.push('/')
const goBack = () => router.back()

const sections = [
  {
    icon: Rocket,
    title: '快速开始',
    content: `
      <ol>
        <li>使用管理员分配的账号密码登录系统。</li>
        <li>登录后自动进入对话页面，选择需要的智能体即可开始对话。</li>
        <li>在左侧边栏可以切换对话、查看历史记录、管理知识库等。</li>
      </ol>
    `
  },
  {
    icon: MessagesSquare,
    title: '智能体对话',
    content: `
      <ul>
        <li><strong>新建对话</strong>：点击左侧边栏的"新建对话"按钮，选择目标智能体后开始。</li>
        <li><strong>上传附件</strong>：在对话框左侧的回形针图标可以上传文件，智能体会自动读取附件内容。</li>
        <li><strong>消息反馈</strong>：每条 AI 回复下方可以点赞或点踩，帮助优化回复质量。</li>
        <li><strong>语音朗读</strong>：点击回复消息的喇叭图标，可以使用语音朗读功能（需浏览器支持）。</li>
      </ul>
    `
  },
  {
    icon: Library,
    title: '知识库管理',
    content: `
      <ul>
        <li><strong>创建知识库</strong>：在"知识库"页面点击"新建"，选择向量库类型（Milvus / FAISS）后创建。</li>
        <li><strong>上传文件</strong>：进入知识库详情，点击上传按钮，支持 Markdown、PDF、Word、TXT、HTML 等格式。</li>
        <li><strong>文件状态</strong>：文件会依次经历"已上传 → 解析中 → 待入库 → 已入库"四个阶段，可在文件列表查看实时状态。</li>
        <li><strong>知识导图</strong>：知识库详情页的"知识导图"标签页可自动生成文件分类树状图，方便快速浏览知识结构。</li>
      </ul>
    `
  },
  {
    icon: Settings,
    title: '个人设置',
    content: `
      <ul>
        <li><strong>主题切换</strong>：点击右上角头像，在下拉菜单中可切换浅色/深色模式和主题色系。</li>
        <li><strong>适老化</strong>：下拉菜单中的"适老化设置"提供大号字体、自动朗读等辅助功能。</li>
        <li><strong>账户管理</strong>：点击头像菜单中的用户名可打开账户设置，修改密码和个人信息。</li>
      </ul>
    `
  },
  {
    icon: CircleHelp,
    title: '常见问题',
    content: `
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
    `
  }
]
</script>

<style lang="less" scoped>
.help-view {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: var(--gray-10);
  background-image: radial-gradient(var(--gray-200) 1px, transparent 1px);
  background-size: 24px 24px;
}

.help-navbar {
  padding: 24px 0;
  z-index: 10;

  .navbar-content {
    max-width: 900px;
    margin: 0 auto;
    padding: 0 40px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .brand-container {
    display: flex;
    align-items: center;
    gap: 12px;
  }
}

.brand-text {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  line-height: 1;
  display: flex;
  align-items: center;
  gap: 12px;

  .brand-main {
    color: var(--main-color);
  }

  .brand-separator {
    width: 4px;
    height: 4px;
    background-color: var(--gray-400);
    border-radius: 50%;
  }

  .brand-sub {
    color: var(--gray-600);
    font-size: 18px;
  }
}

.help-main {
  flex: 1;
  display: flex;
  justify-content: center;
  padding: 0 20px 60px;
}

.help-content {
  width: 100%;
  max-width: 760px;
}

.help-section {
  background: var(--gray-0);
  border-radius: 12px;
  padding: 28px 32px;
  margin-bottom: 20px;
  border: 1px solid var(--gray-100);
}

.section-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 18px;
  font-weight: 600;
  color: var(--gray-1000);
  margin: 0 0 16px;

  svg {
    color: var(--main-color);
  }
}

.section-body {
  color: var(--gray-700);
  font-size: 14px;
  line-height: 1.8;

  :deep(ul),
  :deep(ol) {
    padding-left: 20px;
    margin: 0;
  }

  :deep(li) {
    margin-bottom: 8px;
  }

  :deep(strong) {
    color: var(--gray-1000);
  }

  :deep(details) {
    margin-bottom: 12px;
    border: 1px solid var(--gray-100);
    border-radius: 8px;
    overflow: hidden;

    &[open] summary {
      border-bottom: 1px solid var(--gray-100);
    }
  }

  :deep(summary) {
    padding: 12px 16px;
    font-weight: 500;
    color: var(--gray-800);
    cursor: pointer;
    user-select: none;

    &:hover {
      background-color: var(--gray-10);
    }
  }

  :deep(details > p) {
    padding: 12px 16px;
    margin: 0;
    color: var(--gray-600);
  }
}
</style>

<style lang="less">
:root.dark .help-section {
  border-color: var(--gray-100);
}
</style>
