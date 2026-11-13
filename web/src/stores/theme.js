import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { theme } from 'ant-design-vue'

// 色系定义：key → { label, primary(对应 --main-600), bright(对应 --main-bright) }
export const COLOR_SCHEMES = {
  amber: { label: '琥珀', primary: '#d46b08', bright: '#fa8c16' },
  blue: { label: '海蓝', primary: '#0050b3', bright: '#1890ff' },
  green: { label: '翠绿', primary: '#2e7d32', bright: '#4caf50' },
  teal: { label: '青碧', primary: '#00796b', bright: '#009688' },
}

export const useThemeStore = defineStore('theme', () => {
  const savedTheme = localStorage.getItem('theme')
  const isDark = ref(savedTheme === 'dark')
  const savedScheme = localStorage.getItem('color_scheme')
  const colorScheme = ref(COLOR_SCHEMES[savedScheme] ? savedScheme : 'teal')

  // 公共主题配置
  const commonTheme = computed(() => ({
    token: {
      fontFamily:
        "'HarmonyOS Sans SC', Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Fira Sans', 'Droid Sans', 'Helvetica Neue', sans-serif;",
      colorPrimary: COLOR_SCHEMES[colorScheme.value].primary,
      colorLink: 'var(--main-color)',
      colorLinkHover: 'var(--main-600)',
      colorLinkActive: 'var(--main-800)',
      borderRadius: 8,
      wireframe: false,
    },
  }))

  // 浅色主题配置
  const lightTheme = computed(() => ({ ...commonTheme.value }))

  // 深色主题配置
  const darkTheme = computed(() => ({
    ...commonTheme.value,
    algorithm: theme.darkAlgorithm,
  }))

  // 当前主题配置
  const currentTheme = computed(() => (isDark.value ? darkTheme.value : lightTheme.value))

  // 切换主题
  function toggleTheme() {
    setTheme(!isDark.value)
  }

  // 设置主题
  function setTheme(dark) {
    isDark.value = dark
    localStorage.setItem('theme', dark ? 'dark' : 'light')
    updateDocumentTheme()
  }

  // 设置色系
  function setColorScheme(scheme) {
    if (!COLOR_SCHEMES[scheme]) return
    colorScheme.value = scheme
    localStorage.setItem('color_scheme', scheme)
    updateDocumentColorScheme()
  }

  // 更新 document 的主题类
  function updateDocumentTheme() {
    if (isDark.value) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }

  // 更新 document 的色系属性（青碧为默认色系，走 :root 不加属性，避免首屏闪烁）
  function updateDocumentColorScheme() {
    if (colorScheme.value === 'teal') {
      document.documentElement.removeAttribute('data-color-scheme')
    } else {
      document.documentElement.setAttribute('data-color-scheme', colorScheme.value)
    }
  }

  // 初始化
  updateDocumentTheme()
  updateDocumentColorScheme()

  return {
    isDark,
    colorScheme,
    colorSchemes: COLOR_SCHEMES,
    currentTheme,
    toggleTheme,
    setTheme,
    setColorScheme,
  }
})
