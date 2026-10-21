/**
 * Demo 模式提示弹窗组件
 *
 * 在 App.vue 中条件渲染，用户必须点击确认才能继续。
 * 使用 localStorage 记录用户已确认，刷新页面不再重复弹窗。
 */

<script setup>
import { ref, onMounted } from 'vue'
import { Modal } from 'ant-design-vue'
import { ExclamationCircleOutlined } from '@ant-design/icons-vue'

const STORAGE_KEY = 'demo-mode-acknowledged'

const visible = ref(false)

onMounted(() => {
  const acknowledged = localStorage.getItem(STORAGE_KEY)
  if (!acknowledged) {
    visible.value = true
  }
})

function handleConfirm() {
  localStorage.setItem(STORAGE_KEY, 'true')
  visible.value = false
}
</script>

<template>
  <a-modal
    v-model:open="visible"
    :mask-closable="false"
    :closable="false"
    :keyboard="false"
    :width="560"
    :footer="null"
    centered
  >
    <div class="demo-notice">
      <div class="demo-notice-icon">
        <ExclamationCircleOutlined />
      </div>
      <h2 class="demo-notice-title">⚠️ 静态演示版本</h2>
      <div class="demo-notice-body">
        <p>您好！欢迎体验<strong>银发智伴 SilverMate</strong>。</p>
        <p>
          当前页面为<strong class="demo-notice-strong">静态演示版本</strong>，由 GitHub Pages 部署，
          旨在展示产品界面与交互设计，<strong>不涉及任何真实 AI 调用或后端服务</strong>。
        </p>
        <div class="demo-notice-keypoints">
          <p class="demo-notice-keypoint">
            <span class="demo-notice-bullet">①</span>
            对话内容、知识库引用均为<strong>预设示例</strong>，非大模型实时生成
          </p>
          <p class="demo-notice-keypoint">
            <span class="demo-notice-bullet">②</span>
            每条 AI 回复顶部会出现<strong class="demo-notice-strong">「静态演示」橙色徽章</strong>，请注意识别
          </p>
          <p class="demo-notice-keypoint">
            <span class="demo-notice-bullet">③</span>
            问到预设未覆盖的问题时，会收到「演示数据未覆盖」的明确提示
          </p>
        </div>
        <p class="demo-notice-hint">💡 如需体验完整功能，请参照 Demo 帖中的 Docker 部署方式本地运行（含 DeepSeek 大模型 + Milvus 知识库检索）。</p>
      </div>
      <div class="demo-notice-footer">
        <a-button type="primary" size="large" block @click="handleConfirm">
          我已了解，进入演示
        </a-button>
      </div>
    </div>
  </a-modal>
</template>

<style scoped>
.demo-notice {
  text-align: center;
  padding: 12px 8px 4px;
}

.demo-notice-icon {
  font-size: 48px;
  color: #fa8c16;
  margin-bottom: 16px;
}

.demo-notice-title {
  font-size: 22px;
  font-weight: 700;
  color: #1a1a1a;
  margin-bottom: 20px;
}

.demo-notice-body {
  text-align: left;
  font-size: 14px;
  line-height: 1.8;
  color: #555;
}

.demo-notice-body p {
  margin-bottom: 10px;
}

.demo-notice-body ul {
  margin: 8px 0 12px 20px;
  padding: 0;
}

.demo-notice-body li {
  margin-bottom: 4px;
  list-style: disc;
}

.demo-notice-hint {
  color: #fa8c16;
  font-size: 13px;
  background: #fff7e6;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid #ffd591;
}

.demo-notice-footer {
  margin-top: 24px;
}

.demo-notice-strong {
  color: #d4380d;
  font-weight: 700;
}

.demo-notice-keypoints {
  background: #fffbe6;
  border: 1px solid #ffe58f;
  border-radius: 8px;
  padding: 12px 16px;
  margin: 12px 0;
}

.demo-notice-keypoint {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin: 6px 0 !important;
  font-size: 13.5px;
  line-height: 1.7;
  color: #595959;
}

.demo-notice-bullet {
  color: #fa8c16;
  font-weight: 700;
  flex-shrink: 0;
}
</style>
