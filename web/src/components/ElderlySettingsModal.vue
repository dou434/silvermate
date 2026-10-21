<template>
  <a-modal
    v-model:open="visible"
    title="适老化设置"
    :width="500"
    :footer="null"
    @ok="handleSave"
  >
    <div class="elderly-settings-panel">
      <!-- 紧急联系人 -->
      <a-form layout="vertical">
        <a-form-item label="紧急联系人电话">
          <a-input
            v-model:value="emergencyContact"
            placeholder="请输入家人或监护人的电话号码"
            allow-clear
            size="large"
          />
          <div class="font-size-preview">
            配置后，紧急求助按钮中的"联系家人"将拨打此号码
          </div>
        </a-form-item>

        <!-- 字号偏好 -->
        <a-form-item label="界面字号">
          <a-radio-group v-model:value="fontSizePref" size="large">
            <a-radio-button value="normal">标准</a-radio-button>
            <a-radio-button value="large">大字</a-radio-button>
            <a-radio-button value="xlarge">超大字</a-radio-button>
          </a-radio-group>
          <div class="font-size-preview" :style="previewStyle">
            这是预览文字：老年人常见健康问题咨询
          </div>
        </a-form-item>

        <!-- 自动朗读 -->
        <a-form-item label="自动朗读回复">
          <a-switch
            v-model:checked="autoRead"
            size="large"
            checked-children="开"
            un-checked-children="关"
          />
          <div class="font-size-preview">
            开启后，AI 每次回复完成会自动语音朗读，方便老人“听”回复
          </div>
        </a-form-item>

        <!-- 提醒铃声 -->
        <a-form-item label="提醒铃声">
          <a-switch
            v-model:checked="alertSound"
            size="large"
            checked-children="开"
            un-checked-children="关"
          />
          <div class="font-size-preview">
            开启后，提醒到点会先响铃再朗读。关掉则没有任何声音提示
          </div>
        </a-form-item>

        <!-- 主题色 -->
        <a-form-item label="主题色">
          <div class="color-scheme-options">
            <button
              v-for="(scheme, key) in COLOR_SCHEMES"
              :key="key"
              type="button"
              class="color-scheme-option"
              :class="{ active: currentColorScheme === key }"
              @click="setColorScheme(key)"
            >
              <span class="color-scheme-dot" :style="{ background: scheme.bright }" />
              <span class="color-scheme-name">{{ scheme.label }}</span>
            </button>
          </div>
        </a-form-item>

        <!-- 保存按钮 -->
        <div style="display: flex; gap: 12px; margin-top: 24px;">
          <a-button type="primary" size="large" style="flex: 1; min-height: 48px;" @click="handleSave">
            保存设置
          </a-button>
          <a-button size="large" style="min-height: 48px;" @click="visible = false">
            取消
          </a-button>
        </div>
      </a-form>
    </div>
  </a-modal>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { playAlertChime } from '@/composables/useAlertChime'
import { useThemeStore, COLOR_SCHEMES } from '@/stores/theme'

const themeStore = useThemeStore()
const currentColorScheme = computed(() => themeStore.colorScheme)
const setColorScheme = (key) => themeStore.setColorScheme(key)

const props = defineProps({
  open: { type: Boolean, default: false },
})
const emit = defineEmits(['update:open'])

const visible = computed({
  get: () => props.open,
  set: (v) => emit('update:open', v),
})

const emergencyContact = ref('')
const fontSizePref = ref('large')
const autoRead = ref(false)
// 默认开：提醒的核心就是"要被听见"，默认关等于没做这个功能
const alertSound = ref(true)

// 初始化：从 localStorage 读取
const savedContact = localStorage.getItem('elderly_emergency_contact')
if (savedContact) emergencyContact.value = savedContact

const savedFont = localStorage.getItem('elderly_font_size')
if (savedFont) fontSizePref.value = savedFont

const savedAutoRead = localStorage.getItem('elderly_auto_read')
if (savedAutoRead === 'true') autoRead.value = true

// 只有明确存过 'false' 才算关；没存过按默认开处理
if (localStorage.getItem('elderly_alert_sound') === 'false') alertSound.value = false

const previewStyle = computed(() => {
  const sizes = { normal: '14px', large: '18px', xlarge: '22px' }
  return { fontSize: sizes[fontSizePref.value] || '18px' }
})

function handleSave() {
  // 保存紧急联系人
  localStorage.setItem('elderly_emergency_contact', emergencyContact.value)

  // 保存字号偏好
  localStorage.setItem('elderly_font_size', fontSizePref.value)
  applyFontSize(fontSizePref.value)

  // 保存自动朗读设置
  localStorage.setItem('elderly_auto_read', autoRead.value ? 'true' : 'false')

  // 保存提醒铃声设置
  localStorage.setItem('elderly_alert_sound', alertSound.value ? 'true' : 'false')

  // 点保存本身就是一次用户手势，此时试听能让老人当场确认音量是否合适
  if (alertSound.value) playAlertChime()

  // 通知紧急按钮组件更新
  window.dispatchEvent(new Event('elderly-contact-updated'))

  message.success('设置已保存')
  visible.value = false
}

function applyFontSize(pref) {
  const sizes = { normal: '16px', large: '18px', xlarge: '22px' }
  document.documentElement.style.setProperty('--elderly-font-size', sizes[pref])
}

// 页面加载时应用已保存的字号（放在 onMounted 中执行，避免 setup 阶段操作 DOM）
onMounted(() => {
  applyFontSize(fontSizePref.value)
})
</script>

<style scoped>
.elderly-settings-panel {
  padding: 16px 0;
}

.elderly-settings-panel :deep(.ant-form-item-label > label) {
  font-size: 16px;
  font-weight: 500;
}

.elderly-settings-panel :deep(.ant-input),
.elderly-settings-panel :deep(.ant-select-selector) {
  font-size: 16px !important;
  min-height: 44px !important;
}

.font-size-preview {
  padding: 12px 16px;
  background: var(--gray-50, #f5f7f7);
  border-radius: 8px;
  margin-top: 8px;
  color: var(--gray-700, #4c4d4d);
  line-height: 1.6;
}

.color-scheme-options {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.color-scheme-option {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 10px 16px;
  border: 2px solid var(--gray-200, #e4e6e6);
  border-radius: 10px;
  background: var(--gray-0, #fff);
  cursor: pointer;
  transition: border-color 0.2s ease, transform 0.15s ease;

  &:hover {
    transform: translateY(-2px);
  }

  &.active {
    border-color: var(--gray-800, #323333);
  }
}

.color-scheme-dot {
  width: 28px;
  height: 28px;
  border-radius: 50%;
}

.color-scheme-name {
  font-size: 14px;
  color: var(--gray-800, #323333);
}
</style>
