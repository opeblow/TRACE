import axios from 'axios'
import { getWorkspace } from './workspace'
import type { AnalysisResult, JobStatus } from './types'

// Configure this public URL for each deployment. No server secret belongs in
// the browser bundle. An empty value uses same-origin requests (and fails
// visibly if the API has not been reverse-proxied there).
const API_URL = process.env.NEXT_PUBLIC_API_URL || ''

export const api = axios.create({
  baseURL: API_URL,
  timeout: 20000,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use(config => {
  const workspace = getWorkspace()
  if (workspace) config.headers.set('X-Trace-Workspace', workspace)
  return config
})

export const errorMessage = (err: unknown, fallback: string) => {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  return typeof detail === 'string' ? detail : fallback
}

const idempotencyKey = () => crypto.getRandomValues(new Uint32Array(4)).reduce((acc, n) => acc + n.toString(36), 'ui-')

export const analyzeWallet = async (address: string): Promise<AnalysisResult> => {
  const response = await api.post('/api/v1/wallets/analyze', { address })
  return response.data
}

export const rememberLabel = async (wallet: string, counterparty: string, label: string) => {
  const response = await api.post('/api/v1/memories', { memory_type: 'counterparty_label', wallet, subject: counterparty, value: label, consent: true }, { headers: { 'Idempotency-Key': idempotencyKey() } })
  return response.data as { job_id: string }
}

export const submitAlertFeedback = async (digest: string, wallet: string, label: 'expected' | 'needs_review' | 'incorrect', reason: string) => {
  const response = await api.post(`/api/v1/alerts/${encodeURIComponent(digest)}/feedback`, { wallet, label, reason, consent: true }, { headers: { 'Idempotency-Key': idempotencyKey() } })
  return response.data as { job_id: string }
}

export const rememberSummary = async (wallet: string, summary: string) => {
  const response = await api.post('/api/v1/memories', { memory_type: 'investigation_summary', wallet, value: summary, consent: true }, { headers: { 'Idempotency-Key': idempotencyKey() } })
  return response.data as { job_id: string }
}

export const getMemoryJob = async (jobId: string): Promise<JobStatus> => {
  const response = await api.get(`/api/v1/memories/jobs/${encodeURIComponent(jobId)}`)
  return response.data
}

/** Poll until Walrus Memory reports the job finished. Never reports success early. */
export async function waitForMemoryJob(jobId: string, onTick: (elapsedSeconds: number) => void, timeoutMs = 150_000): Promise<JobStatus> {
  const started = Date.now()
  let delay = 1500
  while (Date.now() - started < timeoutMs) {
    await new Promise(resolve => setTimeout(resolve, delay))
    onTick(Math.round((Date.now() - started) / 1000))
    try {
      const status = await getMemoryJob(jobId)
      if (status.status !== 'pending') return status
    } catch (err) {
      const code = (err as { response?: { status?: number } })?.response?.status
      if (code === 404) return { job_id: jobId, status: 'failed', error: 'Walrus Memory does not know this job.' }
      // transient (network / 5xx / 429): keep polling within the time budget
    }
    delay = Math.min(delay * 1.4, 5000)
  }
  return { job_id: jobId, status: 'pending', error: 'Still processing. Check the Memory Centre shortly; it has not been confirmed yet.' }
}

export const getMemories = async (wallet?: string) => {
  const response = await api.get('/api/v1/memories', { params: { wallet } })
  return response.data as { namespace_ref: string; storage: string; memories: Array<{ memory_id: string; memory_type: string; wallet: string; subject: string; value: string; reason: string; created_at: string; verified: boolean; source_type: string }> }
}

export const forgetAllMemories = async () => {
  const response = await api.delete('/api/v1/memories', { data: { confirm: 'DELETE' } })
  return response.data as { deleted: number; message: string }
}
