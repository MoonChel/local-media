import { ref } from 'vue'

export function useNotification() {
  const message = ref('')
  const type = ref('error') // 'error' | 'success' | 'info'

  function showError(msg, autoHide = true) {
    message.value = msg
    type.value = 'error'
    if (autoHide) {
      setTimeout(() => {
        if (message.value === msg) {
          message.value = ''
        }
      }, 3000)
    }
  }

  function showSuccess(msg, autoHide = true) {
    message.value = msg
    type.value = 'success'
    if (autoHide) {
      setTimeout(() => {
        if (message.value === msg) {
          message.value = ''
        }
      }, 2000)
    }
  }

  function showInfo(msg, autoHide = true) {
    message.value = msg
    type.value = 'info'
    if (autoHide) {
      setTimeout(() => {
        if (message.value === msg) {
          message.value = ''
        }
      }, 2000)
    }
  }

  function clear() {
    message.value = ''
  }

  return {
    message,
    type,
    showError,
    showSuccess,
    showInfo,
    clear,
  }
}
