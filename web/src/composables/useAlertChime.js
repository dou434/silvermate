/**
 * 提醒铃声 composable - 用 Web Audio 现场合成，不依赖 TTS 开关、也不需要音频文件
 *
 * 为什么不用 <audio src="ding.mp3">：
 * 需要额外带资源文件，且 play() 返回的 Promise 还要单独处理拒绝，
 * 合成音可以精确控制音高、包络和时长，也不占网络请求。
 *
 * 为什么必须"解锁"：
 * 浏览器自动播放策略要求页面先收到一次用户手势，否则 AudioContext 会停在
 * suspended，播放静默失败（不报错，只是没声音）。
 * 因此这里在首次 pointerdown / keydown 时 resume，之后所有提醒都能正常响。
 */
import { onMounted, onUnmounted, ref } from 'vue'

/** 音量上限：0.22 是试出来的。开到 1.0 时手机外放会破音，反而吓人 */
const PEAK_GAIN = 0.22
/** 636Hz / 880Hz 这类中低频：老年性耳聋先损失高频，2kHz 以上听不见只觉得刺耳 */
const NOTES = [660, 880, 660, 880]
const NOTE_GAP_SECONDS = 0.55
const NOTE_DURATION_SECONDS = 0.45
/** 泛音音量占基频的比例，让铃声像门铃而不是电子报警器 */
const OVERTONE_RATIO = 0.25

/** 全局单例：Chrome 对同时存在的 AudioContext 有数量上限，按次创建会耗尽 */
let audioContext = null

/**
 * 取（或惰性创建）全局 AudioContext。
 *
 * @returns {AudioContext | null} 浏览器不支持时返回 null
 */
function ensureContext() {
  if (audioContext) return audioContext
  if (typeof window === 'undefined') return null

  const AudioCtor = window.AudioContext || window.webkitAudioContext
  if (!AudioCtor) return null

  audioContext = new AudioCtor()
  return audioContext
}

/**
 * 播放一个音符：正弦基频 + 2 倍频泛音，瞬间起音 + 指数衰减。
 *
 * @param {AudioContext} context 音频上下文
 * @param {number} frequency 基频（Hz）
 * @param {number} startAt 相对 context 时间轴的起始时刻（秒）
 */
function playNote(context, frequency, startAt) {
  const endAt = startAt + NOTE_DURATION_SECONDS

  // 基频
  const oscillator = context.createOscillator()
  const gain = context.createGain()
  oscillator.type = 'sine'
  oscillator.frequency.value = frequency
  gain.gain.setValueAtTime(0.0001, startAt)
  gain.gain.exponentialRampToValueAtTime(PEAK_GAIN, startAt + 0.02)
  gain.gain.exponentialRampToValueAtTime(0.0001, endAt)
  oscillator.connect(gain).connect(context.destination)
  oscillator.start(startAt)
  oscillator.stop(endAt)

  // 泛音：只是让音色厚一点，衰减比基频快
  const overtone = context.createOscillator()
  const overtoneGain = context.createGain()
  overtone.type = 'sine'
  overtone.frequency.value = frequency * 2
  overtoneGain.gain.setValueAtTime(0.0001, startAt)
  overtoneGain.gain.exponentialRampToValueAtTime(PEAK_GAIN * OVERTONE_RATIO, startAt + 0.02)
  overtoneGain.gain.exponentialRampToValueAtTime(0.0001, startAt + NOTE_DURATION_SECONDS * 0.7)
  overtone.connect(overtoneGain).connect(context.destination)
  overtone.start(startAt)
  overtone.stop(endAt)
}

/**
 * 在用户手势里解锁音频上下文。
 *
 * 浏览器只在用户交互后才允许有声播放，调用方应在首次点击/按键时调用本函数。
 * 已经处于 running 时重复调用无副作用。
 */
export function unlockAlertChime() {
  const context = ensureContext()
  if (!context) return

  if (context.state === 'suspended') {
    // 手势里 resume 才有效；失败也不抛到业务层，铃声只是没有，不应阻断提醒弹窗
    context.resume().catch(() => {})
  }
}

/**
 * 播放提醒铃声（4 声，约 2 秒）并尝试震动。
 *
 * 若页面还没收到过用户手势，浏览器会拦下声音，此处静默失败——
 * 弹窗照常出现，不因铃声失败而影响提醒本身。
 */
export function playAlertChime() {
  const context = ensureContext()
  if (!context) return

  // 未解锁时必须直接放弃排程，而不是"排了等解锁"：
  // suspended 状态下音频时钟是冻结的，已排程的音符会在老人下一次点击、
  // 上下文恢复的瞬间一起补响，变成一串莫名其妙的迟到铃声。
  if (context.state !== 'running') {
    context.resume().catch(() => {})
    return
  }

  const startAt = context.currentTime + 0.05
  NOTES.forEach((frequency, index) => {
    playNote(context, frequency, startAt + index * NOTE_GAP_SECONDS)
  })

  // 安卓有效，iOS 直接忽略，零成本
  if (typeof navigator !== 'undefined' && typeof navigator.vibrate === 'function') {
    navigator.vibrate([300, 150, 300])
  }
}

/**
 * 组件内使用：注册首次手势解锁监听，并暴露是否支持。
 *
 * @returns {{ isSupported: import('vue').Ref<boolean> }}
 */
export function useAlertChime() {
  const isSupported = ref(false)
  let removeListeners = null

  onMounted(() => {
    if (typeof window === 'undefined') return
    isSupported.value = Boolean(window.AudioContext || window.webkitAudioContext)
    if (!isSupported.value) return

    const handler = () => unlockAlertChime()
    // capture 保证早于业务逻辑执行，登录页点一下就已完成解锁
    const options = { capture: true, passive: true }
    document.addEventListener('pointerdown', handler, options)
    document.addEventListener('keydown', handler, options)
    removeListeners = () => {
      document.removeEventListener('pointerdown', handler, options)
      document.removeEventListener('keydown', handler, options)
    }
  })

  onUnmounted(() => {
    removeListeners?.()
    removeListeners = null
  })

  return { isSupported }
}
