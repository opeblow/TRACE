'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import FindingCard from '@/components/FindingCard'
import SiteHeader from '@/components/SiteHeader'
import { analyzeWallet, errorMessage } from '@/lib/api'
import { RESULT_KEY, shortHash, suiscanTx, type AnalysisResult, type MemoryBlock } from '@/lib/types'

const prettyDate = (value?: string) => {
  if (!value) return 'Unavailable'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Unavailable' : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}
const partialReasonCopy: Record<string, string> = {
  provider_has_more_history: 'More history is available than this first page includes.',
  insufficient_interpretable_history: 'History was too limited to assess patterns.',
  some_transactions_lack_native_sui_balance_changes: 'Some returned transactions did not include interpretable native SUI balance changes.',
}
const activityDate = (value?: string | number | null) => {
  if (value == null) return 'Timestamp unavailable'
  const date = new Date(Number(value))
  return Number.isNaN(date.getTime()) ? 'Timestamp unavailable' : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}
const signedAmount = (value: string | number) => { const text = String(value); return text.startsWith('-') ? `−${text.slice(1)}` : text === '0' ? '0' : `+${text}` }

function MemoryPanel({ memory }: { memory?: MemoryBlock }) {
  if (!memory) return null
  const tone = memory.status === 'used' ? 'border-[#b9d7c6] bg-[#f3f9f5] text-[#14523d]'
    : memory.status === 'unavailable' || memory.status === 'not_configured' || memory.status === 'no_workspace' ? 'border-[#e9d9b8] bg-[#fffaf0] text-[#705c32]'
    : 'border-[#dce4de] bg-white text-[#40564b]'
  const title = memory.status === 'used' ? `Walrus Memory: ${memory.recalled_count} recalled, result changed`
    : memory.status === 'recalled' ? `Walrus Memory: ${memory.recalled_count} recalled, no finding affected`
    : memory.status === 'none' ? 'Walrus Memory: nothing saved for this wallet yet'
    : 'Stateless analysis'
  return (
    <section aria-label="Memory used in this analysis" role="status" className={`mt-4 rounded-xl border px-5 py-4 text-sm leading-6 ${tone}`}>
      <p className="font-semibold">{title}</p>
      <p>{memory.message}</p>
      {memory.memories.length > 0 && (
        <ul className="mt-2 space-y-1 text-xs">
          {memory.memories.map(m => (
            <li key={m.memory_id}>
              <span className="font-medium">{m.memory_type.replace('_', ' ')}</span>: {m.memory_type === 'counterparty_label' ? `${shortHash(m.subject)} → “${m.value || 'label removed'}”` : m.memory_type === 'alert_feedback' ? `${shortHash(m.subject, 6, 4)} marked ${m.value.replace('_', ' ')}` : m.value}
              <span className="text-[#5f6c66]"> · saved {prettyDate(m.created_at)} · {m.used ? 'used in this result' : 'not relevant to current findings'}</span>
            </li>
          ))}
        </ul>
      )}
      {memory.namespace_ref && <p className="mt-2 text-xs text-[#5f6c66]">Workspace ref <span className="font-mono">{memory.namespace_ref}</span> · <Link href="/memories" className="underline underline-offset-4">Open Memory Centre</Link></p>}
    </section>
  )
}

export default function WalletOverviewPage() {
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [invalidStoredData, setInvalidStoredData] = useState(false)
  const [view, setView] = useState<'memory' | 'stateless'>('memory')
  const [rerunning, setRerunning] = useState(false)
  const [rerunError, setRerunError] = useState('')

  useEffect(() => {
    try {
      const raw = localStorage.getItem(RESULT_KEY)
      if (!raw) return
      const parsed = JSON.parse(raw)
      if (parsed && typeof parsed === 'object') setResult(parsed)
      else setInvalidStoredData(true)
    } catch { setInvalidStoredData(true) }
  }, [])

  const rerun = async () => {
    if (!result?.address || rerunning) return
    setRerunning(true); setRerunError('')
    try {
      const fresh = await analyzeWallet(result.address)
      try { localStorage.setItem(RESULT_KEY, JSON.stringify(fresh)) } catch { /* display still works */ }
      setResult(fresh); setView('memory')
      window.scrollTo({ top: 0, behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' })
    } catch (err) {
      setRerunError(errorMessage(err, 'TRACE could not refresh this analysis. The previous result is still shown.'))
    } finally { setRerunning(false) }
  }

  const memory = result?.memory
  const findings = (view === 'stateless' ? memory?.stateless?.anomalies : result?.analysis?.anomalies) ?? []
  const activities = result?.activity?.items ?? []
  const sourceLabel = (result?.snapshot?.sources ?? []).map(source => source.replaceAll('_', ' ')).join(', ')
  const baselineEstablished = result?.analysis?.baseline?.status === 'established'
  const thinHistory = result?.analysis?.baseline?.status === 'thin_history'
  const canCompare = Boolean(memory?.changed_result)
  const interactive = view === 'memory' && Boolean(memory && memory.status !== 'no_workspace' && memory.status !== 'not_configured')

  return (<main className="min-h-screen">
    <SiteHeader />
    <section className="mx-auto max-w-6xl px-5 py-10 sm:px-8 sm:py-14">
      {!result ? <div className="rounded-2xl border border-[#dce4de] bg-white p-8 text-center sm:p-12"><p className="text-xs font-semibold tracking-[.14em] text-[#176b50]">WALLET OVERVIEW</p><h1 className="mt-3 text-3xl font-semibold tracking-[-.04em]">No analysis in this session</h1><p role={invalidStoredData ? 'alert' : undefined} className="mx-auto mt-3 max-w-lg text-sm leading-6 text-[#5f6c66]">{invalidStoredData ? 'The saved analysis could not be read. Start a new analysis to continue.' : 'Analyze a Sui address to see its available balance, activity summary, and explainable findings.'}</p><Link href="/analyze" className="mt-6 inline-flex rounded-lg bg-[#176b50] px-4 py-3 text-sm font-semibold text-white hover:bg-[#10533d]">Analyze a wallet</Link></div> : <>
        <div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
          <div><p className="text-xs font-semibold tracking-[.14em] text-[#176b50]">WALLET OVERVIEW</p><h1 className="mt-3 text-3xl font-semibold tracking-[-.05em] sm:text-4xl">Analysis summary</h1><p className="mt-3 font-mono text-sm text-[#5f6c66]" title={result.address}>{result.address ? shortHash(result.address, 10, 8) : 'Address unavailable'}</p></div>
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={rerun} disabled={rerunning} aria-busy={rerunning} className="inline-flex w-fit rounded-lg bg-[#176b50] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#10533d] disabled:bg-[#a9bbb0]">{rerunning ? 'Refreshing…' : 'Re-run analysis'}</button>
            <Link href="/analyze" className="inline-flex w-fit rounded-lg border border-[#cbd7ce] bg-white px-4 py-2.5 text-sm font-medium hover:bg-[#f3f5f1]">Analyze another</Link>
          </div>
        </div>
        {rerunError && <p role="alert" className="mt-4 rounded-lg border border-[#eed2c7] bg-[#fff8f5] px-4 py-3 text-sm text-[#8d3d25]">{rerunError}</p>}
        <div className="mt-8 grid gap-4 sm:grid-cols-3">
          {[
            ['Native SUI balance', result.snapshot?.balance != null ? `${result.snapshot.balance} ${result.snapshot.balance_unit || 'SUI'}` : 'Unavailable', result.snapshot?.balance == null ? 'Provider did not return a balance' : 'Returned by Tatum (Sui gRPC)'],
            ['Transactions observed', String(result.snapshot?.activity_count ?? activities.length), result.activity?.has_more ? 'Most recent page only; more history exists' : 'In the retrieved page'],
            ['Findings', baselineEstablished ? String(result.analysis?.anomaly_count ?? findings.length) : 'Not assessed', baselineEstablished ? (findings.length ? 'Review the observations below' : 'No outlier under this rule') : 'Insufficient interpretable history'],
          ].map(([label, value, hint]) => <article key={label} className="rounded-xl border border-[#dce4de] bg-white p-5"><p className="text-sm text-[#5f6c66]">{label}</p><p className="mt-3 break-words text-2xl font-semibold tracking-[-.04em] tabular-nums">{value}</p><p className="mt-2 text-xs text-[#6d7972]">{hint}</p></article>)}
        </div>
        <div className="mt-5 flex flex-col gap-2 rounded-xl border border-[#dce4de] bg-white px-5 py-4 text-sm sm:flex-row sm:items-center sm:justify-between"><span><strong className="font-medium">Data retrieved</strong><span className="ml-2 text-[#5f6c66]">{prettyDate(result.snapshot?.fetched_at)}</span></span><span className="text-[#5f6c66]">Network: <strong className="font-medium text-[#17231f]">{result.snapshot?.network ? `Sui ${result.snapshot.network}` : 'Not reported'}</strong>{result.snapshot?.checkpoint_height != null && <> · checkpoint <span className="tabular-nums">{result.snapshot.checkpoint_height}</span></>} · Source: {sourceLabel || 'Not reported'}</span></div>
        <MemoryPanel memory={memory} />
        {thinHistory && <div role="status" className="mt-4 rounded-xl border border-[#e9d9b8] bg-[#fffaf0] px-5 py-4 text-sm leading-6 text-[#705c32]">Fewer than 10 transactions with interpretable SUI balance changes were available. TRACE cannot establish a reliable baseline.</div>}
        {result.analysis?.status === 'partial' && <div role="status" className="mt-4 rounded-xl border border-[#e9d9b8] bg-[#fffaf0] px-5 py-4 text-sm leading-6 text-[#705c32]">This is a partial analysis. {(result.analysis?.partial_reasons ?? []).map(reason => partialReasonCopy[reason] ?? 'Some analysis data is incomplete.').join(' ')}</div>}

        <section className="mt-8 rounded-2xl border border-[#dce4de] bg-white" aria-labelledby="findings-heading">
          <div className="flex flex-col gap-3 border-b border-[#e8ede9] px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
            <div><h2 id="findings-heading" className="font-semibold tracking-[-.02em]">Explainable findings</h2><p className="mt-1 text-sm text-[#5f6c66]">Observed SUI movements compared with this wallet’s available history, highest priority first.</p></div>
            {canCompare && (
              <div role="group" aria-label="Compare results" className="inline-flex w-fit rounded-lg border border-[#cbd7ce] p-0.5 text-xs font-medium">
                <button type="button" aria-pressed={view === 'memory'} onClick={() => setView('memory')} className={`rounded-md px-3 py-1.5 ${view === 'memory' ? 'bg-[#176b50] text-white' : 'text-[#40564b]'}`}>With memory</button>
                <button type="button" aria-pressed={view === 'stateless'} onClick={() => setView('stateless')} className={`rounded-md px-3 py-1.5 ${view === 'stateless' ? 'bg-[#176b50] text-white' : 'text-[#40564b]'}`}>Without memory</button>
              </div>
            )}
          </div>
          {view === 'stateless' && <p className="border-b border-[#e8ede9] bg-[#fafaf7] px-5 py-3 text-xs text-[#5f6c66] sm:px-6">Showing the same chain facts and rule with no recalled memory. Switch back to see what your saved context changed.</p>}
          {findings.length ? <ul className="divide-y divide-[#e8ede9]">{findings.map((item, index) => <FindingCard key={`${view}-${item.transaction_digest ?? index}`} finding={item} wallet={result.address ?? ''} interactive={interactive} onApply={rerun} />)}</ul>
            : <div className="px-5 py-10 text-center sm:px-6"><h3 className="font-medium">{baselineEstablished ? 'No outlier identified under this rule' : 'Not enough history to assess patterns'}</h3><p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-[#5f6c66]">{baselineEstablished ? 'No movement exceeded the current statistical threshold. This does not guarantee the wallet is safe.' : 'The available transaction data was too limited to establish a baseline, so TRACE cannot determine whether activity is unusual.'}</p></div>}
        </section>

        <section className="mt-5 overflow-hidden rounded-2xl border border-[#dce4de] bg-white" aria-labelledby="activity-heading"><div className="border-b border-[#e8ede9] px-5 py-4 sm:px-6"><h2 id="activity-heading" className="font-semibold tracking-[-.02em]">Recent activity</h2><p className="mt-1 text-sm text-[#5f6c66]">{activities.length} transaction records returned for this analysis, newest first.</p></div>
          {activities.length ? <ul className="divide-y divide-[#e8ede9]">{activities.map(item => <li key={item.digest} className="flex flex-col gap-2 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6"><div><p className="font-mono text-sm">{shortHash(item.digest, 10, 8)}</p><p className="mt-1 text-xs text-[#6d7972]">{activityDate(item.timestamp_ms)}{item.counterparty && <> · {item.direction === 'in' ? 'from' : 'to'} <span className="font-mono">{shortHash(item.counterparty, 6, 4)}</span></>}{item.counterparty_label && <span className="ml-1 rounded bg-[#eaf2ed] px-1.5 py-0.5 text-[#176b50]">{item.counterparty_label}</span>}</p></div><div className="flex items-center justify-between gap-4 text-sm sm:justify-end"><span className="tabular-nums text-[#5f6c66]">{item.status === 'failure' ? 'Failed transaction' : item.amount_sui == null ? 'SUI change unavailable' : `${signedAmount(item.amount_sui)} SUI net change`}</span><a className="inline-flex min-h-11 items-center font-medium text-[#176b50] underline underline-offset-4 sm:min-h-0" href={suiscanTx(item.digest)} target="_blank" rel="noreferrer">Explorer</a></div></li>)}</ul> : <div className="px-5 py-8 text-center text-sm text-[#5f6c66]">No transactions were returned by the provider for this query.</div>}
          {result.activity?.has_more && <p className="border-t border-[#e8ede9] bg-[#fafaf7] px-5 py-3 text-xs text-[#6d7972]">This is a bounded first page. Additional activity is available; pagination is not yet implemented.</p>}
        </section>
        <p className="mt-5 text-xs leading-5 text-[#6d7972]">This is an observational analysis, not a security guarantee or financial advice. The analysis result is kept in this browser; labels and feedback you confirm are stored in Walrus Memory for this browser’s workspace. On-chain records are public and cannot be removed by TRACE.</p>
      </>}
    </section></main>
  )
}
