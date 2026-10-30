export type MemoryContext = {
  memory_id: string
  memory_type: string
  summary: string
  created_at: string
  verified: boolean
}

export type Finding = {
  type?: string
  severity?: string
  severity_without_memory?: string
  state?: string
  amount_sui?: string
  threshold_sui?: string
  transaction_digest?: string
  counterparty?: string | null
  direction?: string | null
  rationale?: string
  uncertainty?: number
  confidence?: number
  confidence_factors?: string[]
  robust_z?: number
  rule_version?: string
  memory_context?: MemoryContext[]
  evidence?: Array<{ ref?: string; timestamp?: string | number | null; source?: string }>
}

export type ActivityItem = {
  digest: string
  timestamp_ms?: string | number | null
  checkpoint?: number | null
  status?: string | null
  direction?: string | null
  amount_sui?: string | number | null
  counterparty?: string | null
  counterparty_label?: string | null
}

export type RecalledMemory = {
  memory_id: string
  memory_type: string
  subject: string
  value: string
  reason: string
  created_at: string
  verified: boolean
  used: boolean
}

export type MemoryBlock = {
  status: 'used' | 'recalled' | 'none' | 'unavailable' | 'not_configured' | 'no_workspace'
  message: string
  namespace_ref?: string | null
  recalled_count: number
  changed_result: boolean
  memories: RecalledMemory[]
  effects: Array<{ transaction_digest: string; severity_before: string; severity_after: string; state_after: string; because: string[]; memory_ids: string[] }>
  stateless: { anomalies: Finding[] }
}

export type AnalysisResult = {
  address?: string
  snapshot?: { balance?: string | null; balance_unit?: string; fetched_at?: string; network?: string | null; checkpoint_height?: number | null; sources?: string[]; activity_count?: number }
  analysis?: { baseline?: { status?: string; sample_count?: number }; anomalies?: Finding[]; anomaly_count?: number; status?: string; partial_reasons?: string[]; rule_version?: string }
  activity?: { items?: ActivityItem[]; has_more?: boolean }
  memory?: MemoryBlock
}

export type JobStatus = { job_id: string; status: 'pending' | 'succeeded' | 'failed'; blob_id?: string | null; error?: string | null }

export const RESULT_KEY = 'trace_wallet_result'

export const shortHash = (value: string, head = 8, tail = 6) => (value.length > head + tail + 2 ? `${value.slice(0, head)}…${value.slice(-tail)}` : value)
export const walruscanBlob = (blobId: string) => `https://walruscan.com/mainnet/blob/${encodeURIComponent(blobId)}`
export const suiscanTx = (digest: string) => `https://suiscan.xyz/mainnet/tx/${encodeURIComponent(digest)}`
export const suiscanAccount = (address: string) => `https://suiscan.xyz/mainnet/account/${encodeURIComponent(address)}`
