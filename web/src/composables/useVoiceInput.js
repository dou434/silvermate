/**
 * 语音输入 composable - 使用 Web Speech API
 * 支持 Chrome/Edge/Safari，不支持 Firefox
 */
import { ref, onMounted, onUnmounted } from 'vue'

export function useVoiceInput(onResult) {
  const isRecording = ref(false)
  const isSupported = ref(false)
  const interimText = ref('')
  let recognition = null

  onMounted(() => {
    if (typeof window === 'undefined') return
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition
    if (SpeechRecognition) {
      isSupported.value = true
      recognition = new SpeechRecognition()
      recognition.lang = 'zh-CN'
      recognition.continuous = true
      recognition.interimResults = true

      recognition.onstart = () => {
        isRecording.value = true
      }

      recognition.onresult = (event) => {
        let finalText = ''
        let interim = ''
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = event.results[i][0].transcript
          if (event.results[i].isFinal) {
            finalText += transcript
          } else {
            interim += transcript
          }
        }
        interimText.value = interim
        if (finalText && typeof onResult === 'function') {
          onResult(finalText)
        }
      }

      recognition.onerror = (event) => {
        console.warn('语音识别错误:', event.error)
        isRecording.value = false
      }

      recognition.onend = () => {
        isRecording.value = false
        interimText.value = ''
      }
    }
  })

  onUnmounted(() => {
    if (recognition) {
      try {
        // 清理事件监听，防止内存泄漏
        recognition.onstart = null
        recognition.onresult = null
        recognition.onerror = null
        recognition.onend = null
        recognition.stop()
      } catch {
        // 卸载阶段识别器可能已失效，忽略
      }
      recognition = null
    }
  })

  function toggleRecording() {
    if (!isSupported.value || !recognition) return
    if (isRecording.value) {
      recognition.stop()
      isRecording.value = false
    } else {
      try {
        recognition.start()
        // isRecording 由 onstart 回调设置，避免 start 失败时状态不一致
      } catch (e) {
        console.warn('启动语音识别失败:', e)
        isRecording.value = false
      }
    }
  }

  function stopRecording() {
    if (recognition && isRecording.value) {
      recognition.stop()
      isRecording.value = false
    }
  }

  return {
    isRecording,
    isSupported,
    interimText,
    toggleRecording,
    stopRecording,
  }
}
