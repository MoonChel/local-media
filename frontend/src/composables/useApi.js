import { ref } from 'vue'

export function useApi() {
  const loading = ref(false)
  const error = ref('')

  async function fetchApi(url, options = {}) {
    loading.value = true
    error.value = ''
    try {
      const res = await fetch(url, options)
      if (!res.ok) {
        const text = await res.text()
        let errorMsg = text
        try {
          const json = JSON.parse(text)
          errorMsg = json.detail || text
        } catch {}
        throw new Error(`${res.status}: ${errorMsg}`)
      }
      return await res.json()
    } catch (e) {
      error.value = String(e)
      throw e
    } finally {
      loading.value = false
    }
  }

  async function postApi(url, data) {
    return fetchApi(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
  }

  async function deleteApi(url) {
    return fetchApi(url, { method: 'DELETE' })
  }

  function clearError() {
    error.value = ''
  }

  return {
    loading,
    error,
    fetchApi,
    postApi,
    deleteApi,
    clearError,
  }
}
