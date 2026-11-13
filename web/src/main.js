import { createApp } from 'vue'
import { createPinia } from 'pinia'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'

import App from './App.vue'
import router from './router'

import 'ant-design-vue/dist/reset.css'
import '@/assets/css/main.css'
import '@/assets/css/elderly-friendly.css'

// Demo 模式：拦截 API 返回假数据
if (import.meta.env.VITE_DEMO_MODE === 'true') {
  const { installMockInterceptor } = await import('./demo/mockInterceptor')
  installMockInterceptor()
}

const app = createApp(App)
const pinia = createPinia()
pinia.use(piniaPluginPersistedstate)

app.use(pinia)
app.use(router)

// 预加载信息配置
import { useInfoStore } from '@/stores/info'
const infoStore = useInfoStore()
infoStore.loadInfoConfig()

app.mount('#app')
