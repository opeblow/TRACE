'use client'

import { useCallback, useState } from 'react'
import { errorMessage, waitForMemoryJob } from '@/lib/api'
import { shortHash, walruscanBlob } from '@/lib/types'

export type JobState =
  | { phase: 'idle' }
  | { phase: 'submitting' }
  | { phase: 'waiting'; jobId: string; elapsed: number }
  | { phase: 'stored'; jobId: string; blobId: string }
  | { phase: 'failed'; message: string }
  | { phase: 'unconfirmed'; jobId: string; message: string }

/** Runs a memory write and follows the Walrus job until it really completes. */
export function useMemoryJob() {
  const [state, setState] = useState<JobState>({ phase: 'idle' })
  const run = useCallback(async (submit: () => Promise<{ job_id: string }>) => {
    setState({ phase: 'submitting' })
    let jobId: string
    try {
      jobId = (await submit()).job_id
    } catch (err) {
      setState({ phase: 'failed', message: errorMessage(err, 'TRACE could not submit this memory. Nothing was saved.') })
      return
    }
    setState({ phase: 'waiting', jobId, elapsed: 0 })
    const result = await waitForMemoryJob(jobId, elapsed => setState({ phase: 'waiting', jobId, elapsed }))
    if (result.status === 'succeeded' && result.blob_id) setState({ phase: 'stored', jobId, blobId: result.blob_id })
    else if (result.status === 'failed') setState({ phase: 'failed', message: result.error || 'Walrus Memory reported the write as failed. Nothing was saved.' })
    else setState({ phase: 'unconfirmed', jobId, message: result.error || 'Not confirmed yet.' })
  }, [])
  return { state, run, busy: state.phase === 'submitting' || state.phase === 'waiting' }
}

export function MemoryJobStatus({ state, onApply }: { state: JobState; onApply?: () => void }) {
  if (state.phase === 'idle') return null
  const base = 'mt-3 rounded-lg border px-3 py-2.5 text-sm leading-6'
  return (
    <div role="status" aria-live="polite">
      {state.phase === 'submitting' && <p className={`${base} border-[#dce4de] bg-[#fafaf7] text-[#5f6c66]`}>Submitting to Walrus Memory…</p>}
      {state.phase === 'waiting' && (
        <p className={`${base} border-[#dce4de] bg-[#fafaf7] text-[#5f6c66]`}>
          <span className="mr-2 inline-block h-2 w-2 animate-pulse rounded-full bg-[#176b50] motion-reduce:animate-none" aria-hidden="true" />
          Accepted as job <span className="font-mono">{shortHash(state.jobId, 6, 4)}</span>. Waiting for Walrus to encrypt, upload, and index it (<span className="tabular-nums">{state.elapsed}s</span>). Not saved until this completes.
        </p>
      )}
      {state.phase === 'stored' && (
        <div className={`${base} border-[#b9d7c6] bg-[#eef6f1] text-[#14523d]`}>
          <p><strong className="font-semibold">Stored in Walrus Memory.</strong> Blob <a className="font-mono underline underline-offset-4" href={walruscanBlob(state.blobId)} target="_blank" rel="noreferrer">{shortHash(state.blobId, 8, 4)}</a></p>
          {onApply && <button type="button" onClick={onApply} className="mt-2 rounded-md bg-[#176b50] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#10533d]">Re-run analysis with this memory</button>}
        </div>
      )}
      {state.phase === 'failed' && <p className={`${base} border-[#eed2c7] bg-[#fff8f5] text-[#8d3d25]`}>{state.message}</p>}
      {state.phase === 'unconfirmed' && <p className={`${base} border-[#e9d9b8] bg-[#fffaf0] text-[#705c32]`}>{state.message}</p>}
    </div>
  )
}
