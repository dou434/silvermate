<template>
  <div class="register-view">
    <!-- 顶部品牌栏 -->
    <nav class="register-navbar">
      <router-link to="/" class="brand-container">
        <img v-if="brandLogo" :src="brandLogo" :alt="brandOrgName" class="brand-logo" />
        <h1 class="brand-text">{{ brandOrgName || brandName }}</h1>
      </router-link>
    </nav>

    <main class="register-main">
      <div class="register-card">
        <header class="card-header">
          <h2 class="card-title">注册新账号</h2>
          <p class="card-subtitle">填写下面几项即可开始使用</p>
        </header>

        <a-form :model="form" layout="vertical" @finish="handleSubmit">
          <a-form-item label="我的身份" name="identity">
            <a-radio-group v-model:value="form.identity" class="identity-group" button-style="solid">
              <a-radio-button value="elder">我是长辈</a-radio-button>
              <a-radio-button value="child">我是子女</a-radio-button>
            </a-radio-group>
            <p class="identity-hint">{{ identityHint }}</p>
          </a-form-item>

          <a-form-item
            label="登录账号"
            name="uid"
            :rules="[
              { required: true, message: '请输入登录账号' },
              { min: 3, max: 20, message: '长度需为 3-20 位' },
              { pattern: /^[a-zA-Z0-9_]+$/, message: '只能包含字母、数字和下划线' }
            ]"
          >
            <a-input
              v-model:value="form.uid"
              size="large"
              placeholder="例如 zhangsan 或 13800138000"
              autocomplete="username"
              allow-clear
            />
          </a-form-item>

          <a-form-item
            label="显示名称（可留空）"
            name="username"
            :rules="[{ max: 20, message: '最多 20 个字符' }]"
          >
            <a-input v-model:value="form.username" size="large" placeholder="例如 张阿姨" allow-clear />
          </a-form-item>

          <a-form-item
            label="密码"
            name="password"
            :rules="[
              { required: true, message: '请输入密码' },
              { min: 6, message: '密码至少 6 位' }
            ]"
          >
            <a-input-password
              v-model:value="form.password"
              size="large"
              placeholder="至少 6 位"
              autocomplete="new-password"
            />
          </a-form-item>

          <a-form-item
            label="确认密码"
            name="confirmPassword"
            :rules="[
              { required: true, message: '请再次输入密码' },
              { validator: validateConfirmPassword }
            ]"
          >
            <a-input-password
              v-model:value="form.confirmPassword"
              size="large"
              placeholder="再输入一次"
              autocomplete="new-password"
            />
          </a-form-item>

          <a-form-item
            label="手机号（可留空）"
            name="phoneNumber"
            :rules="[{ pattern: /^1[3-9]\d{9}$/, message: '请输入正确的手机号' }]"
          >
            <a-input
              v-model:value="form.phoneNumber"
              size="large"
              placeholder="选填，用于以后找回账号"
              allow-clear
            />
          </a-form-item>

          <a-form-item class="submit-item">
            <a-button type="primary" html-type="submit" size="large" block :loading="loading">
              注册并登录
            </a-button>
          </a-form-item>
        </a-form>

        <div v-if="errorMessage" class="error-message">{{ errorMessage }}</div>

        <div class="login-entry">
          <span>已有账号？</span>
          <router-link to="/login" class="login-link">去登录</router-link>
        </div>
      </div>
    </main>

    <footer class="page-footer">
      <div class="copyright">&copy; {{ new Date().getFullYear() }} {{ brandName }}</div>
    </footer>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useInfoStore } from '@/stores/info'
import { message } from 'ant-design-vue'

const router = useRouter()
const userStore = useUserStore()
const infoStore = useInfoStore()

const brandName = computed(() => infoStore.organization?.name || infoStore.branding?.name || '银发智伴')
const brandOrgName = computed(() => infoStore.organization?.name || '')
const brandLogo = computed(() => infoStore.organization?.logo || '')

const form = reactive({
  uid: '',
  identity: 'elder',
  username: '',
  password: '',
  confirmPassword: '',
  phoneNumber: ''
})

const identityHint = computed(() =>
  form.identity === 'child'
    ? '注册后进入家人关怀页面，可以查看长辈的提醒、留言与紧急求助。'
    : '注册后进入长辈主页，大字大声、一句话就能用。'
)

const loading = ref(false)
const errorMessage = ref('')

/**
 * 校验两次密码是否一致。表单提交时会统一提示，因此这里静默返回 Promise。
 * @returns {Promise<void>}
 */
function validateConfirmPassword() {
  if (form.confirmPassword && form.confirmPassword !== form.password) {
    return Promise.reject(new Error('两次输入的密码不一致'))
  }
  return Promise.resolve()
}

async function handleSubmit() {
  if (form.password !== form.confirmPassword) {
    errorMessage.value = '两次输入的密码不一致'
    return
  }

  loading.value = true
  errorMessage.value = ''

  try {
    await userStore.register({
      uid: form.uid.trim(),
      password: form.password,
      identity: form.identity,
      username: form.username.trim() || undefined,
      phone_number: form.phoneNumber.trim() || undefined
    })

    message.success('注册成功')
    router.push(form.identity === 'child' ? '/family' : '/elder')
  } catch (error) {
    errorMessage.value = error.message || '注册失败，请稍后重试'
  } finally {
    loading.value = false
  }
}
</script>

<style lang="less" scoped>
.register-view {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: var(--gray-25, #fafafa);
}

.register-navbar {
  padding: 20px 32px;
}

.brand-container {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
}

.brand-logo {
  width: 32px;
  height: 32px;
  border-radius: 6px;
}

.brand-text {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--gray-900, #1f2329);
}

.register-main {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px 16px;
}

.register-card {
  width: 100%;
  max-width: 440px;
  padding: 36px 32px 28px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.06);
}

.card-header {
  margin-bottom: 24px;
  text-align: center;
}

.card-title {
  margin: 0 0 8px;
  font-size: 24px;
  font-weight: 600;
  color: var(--gray-900, #1f2329);
}

.card-subtitle {
  margin: 0;
  font-size: 15px;
  color: var(--gray-600, #646a73);
}

.identity-group {
  display: flex;
  width: 100%;
}

.identity-group :deep(.ant-radio-button-wrapper) {
  flex: 1;
  height: 48px;
  line-height: 46px;
  text-align: center;
  font-size: 17px;
}

.identity-hint {
  margin: 8px 0 0;
  font-size: 14px;
  line-height: 1.5;
  color: var(--gray-600, #646a73);
}

.submit-item {
  margin-bottom: 12px;
}

.submit-item :deep(.ant-btn) {
  min-height: 48px;
  font-size: 17px;
}

.error-message {
  padding: 10px 12px;
  background-color: var(--color-error-50, #fff1f0);
  border: 1px solid color-mix(in srgb, var(--color-error-500, #f5222d) 25%, transparent);
  border-radius: 6px;
  color: var(--color-error-700, #a8071a);
  font-size: 14px;
  text-align: center;
}

.login-entry {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 6px;
  margin-top: 18px;
  font-size: 14px;
  color: var(--gray-600, #646a73);
}

.login-link {
  color: var(--main-color, #1677ff);
  font-weight: 500;

  &:hover {
    text-decoration: underline;
  }
}

.page-footer {
  padding: 20px;
  text-align: center;
  font-size: 13px;
  color: var(--gray-500, #8f959e);
}

@media (max-width: 480px) {
  .register-card {
    padding: 28px 20px 20px;
  }
}
</style>
