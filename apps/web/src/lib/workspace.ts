// A per-browser workspace key scopes Walrus Memory (demo mode: there are no user
// accounts). It is random, never derived from a wallet, and only sent to the
// TRACE API, which stores a one-way hash of it as the memory namespace.
const STORAGE_KEY = 'trace_workspace'
const PATTERN = /^[A-Za-z0-9_-]{22,64}$/

const randomKey = () => {
  const bytes = new Uint8Array(24)
  crypto.getRandomValues(bytes)
  return btoa(String.fromCharCode(...bytes)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

export const isValidWorkspace = (value: string) => PATTERN.test(value.trim())

export function getWorkspace(): string | null {
  if (typeof window === 'undefined') return null
  try {
    let key = localStorage.getItem(STORAGE_KEY)
    if (!key || !isValidWorkspace(key)) {
      key = randomKey()
      localStorage.setItem(STORAGE_KEY, key)
    }
    return key
  } catch {
    return null // storage blocked: analysis still works, memory is disabled and disclosed
  }
}

export function setWorkspace(value: string): boolean {
  const key = value.trim()
  if (!isValidWorkspace(key)) return false
  try {
    localStorage.setItem(STORAGE_KEY, key)
    return true
  } catch {
    return false
  }
}
