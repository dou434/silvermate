<template>
  <a-modal
    :open="open"
    :footer="null"
    :closable="false"
    :mask-closable="false"
    centered
    width="min(560px, 92vw)"
    wrap-class-name="reminder-alert-wrap"
    @cancel="handleLater"
  >
    <div class="alert-card">
      <p class="alert-time">{{ timeText }}</p>
      <h2 class="alert-title">{{ item?.title || '该做这件事了' }}</h2>
      <p v-if="item?.content" class="alert-content">{{ item.content }}</p>

      <a-button type="primary" size="large" block class="alert-confirm" @click="$emit('confirm')">
        我收到了
      </a-button>
      <a-button type="text" size="large" block class="alert-later" @click="handleLater">
        先放一边
      </a-button>
    </div>
  </a-modal>
</template>

<script setup>
import { computed } from 'vue'
import dayjs from 'dayjs'

const props = defineProps({
  open: { type: Boolean, default: false },
  /** 到点的提醒（今日提醒项，含 scheduled_at / title / content） */
  item: { type: Object, default: null }
})

const emit = defineEmits(['confirm', 'later'])

const timeText = computed(() => (props.item?.scheduled_at ? dayjs(props.item.scheduled_at).format('HH:mm') : ''))

function handleLater() {
  emit('later')
}
</script>

<style lang="less" scoped>
.alert-card {
  padding: 12px 8px 4px;
  text-align: center;
}

.alert-time {
  margin: 0 0 8px;
  font-size: 56px;
  font-weight: 700;
  line-height: 1;
  color: var(--main-color, #1677ff);
  font-variant-numeric: tabular-nums;
}

.alert-title {
  margin: 0 0 12px;
  font-size: 28px;
  font-weight: 600;
  line-height: 1.35;
  color: var(--gray-900, #1f2329);
}

.alert-content {
  margin: 0 0 24px;
  font-size: 19px;
  line-height: 1.6;
  color: var(--gray-700, #434a54);
}

.alert-confirm {
  min-height: 60px;
  margin-bottom: 10px;
  font-size: 21px;
  border-radius: 14px;
}

.alert-later {
  min-height: 48px;
  font-size: 16px;
  color: var(--gray-500, #8f959e);
}
</style>
