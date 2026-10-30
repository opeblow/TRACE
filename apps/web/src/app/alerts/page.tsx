'use client'

import Link from 'next/link'
import SiteHeader from '@/components/SiteHeader'
import { SeverityChip } from '@/components/FindingCard'
import { RESULT_KEY, type Finding } from '@/lib/types'
import { useEffect, useState } from 'react'

type StoredAnalysis = { address?: string; analysis?: { baseline?: { status?: string }; anomalies?: Finding[] } }

export default function AlertsPage() {
  const [data, setData] = useState<StoredAnalysis | null>(null)
  const [loaded, setLoaded] = useState(false)
  useEffect(() => {
    try {
      const raw = localStorage.getItem(RESULT_KEY)
      if (raw) setData(JSON.parse(raw))
    } catch { setData(null) }
    setLoaded(true)
  }, [])
  const findings = data?.analysis?.anomalies ?? []
  const established = data?.analysis?.baseline?.status === 'established'

  return <main className="min-h-screen"><SiteHeader current="/alerts" />
    <section className="mx-auto max-w-6xl px-5 py-12 sm:px-8 sm:py-16"><p className="text-xs font-semibold tracking-[.14em] text-[#176b50]">WALLET INTELLIGENCE</p><h1 className="mt-3 text-4xl font-semibold tracking-[-.05em]">Insights</h1><p className="mt-3 max-w-2xl leading-7 text-[#5f6c66]">Review notable SUI movements against the history observed for this wallet. An unusual pattern is a reason to look closer, not proof of malicious activity.</p>
      <div className="mt-9 overflow-hidden rounded-2xl border border-[#dce4de] bg-white">
        {!loaded ? <div className="p-8 text-sm text-[#5f6c66]" role="status">Loading this session’s analysis…</div> : !data ? <div className="p-8 text-center sm:p-12"><h2 className="text-xl font-semibold">No saved analysis in this browser</h2><p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-[#5f6c66]">Insights are generated only as part of a wallet analysis and are kept in this browser. They are not stored in an alert history.</p><Link href="/analyze" className="mt-6 inline-flex rounded-lg bg-[#176b50] px-4 py-3 text-sm font-semibold text-white hover:bg-[#10533d]">Analyze a wallet</Link></div> : findings.length ? <ul className="divide-y divide-[#e8ede9]">{findings.map((finding, index) => { const digest = finding.transaction_digest || finding.evidence?.[0]?.ref; return <li key={`${digest || finding.type}-${index}`} className="p-5 sm:p-6"><div className="flex flex-wrap items-center gap-2"><h2 className="font-semibold">{(finding.type || 'Unusual SUI movement').replaceAll('_', ' ')}</h2><SeverityChip severity={finding.severity} />{finding.severity_without_memory && finding.severity_without_memory !== finding.severity && <span className="text-xs text-[#14523d]">memory: {finding.severity_without_memory} → {finding.severity}</span>}</div><p className="mt-2 text-sm leading-6 text-[#5f6c66]">{finding.rationale}</p>{(finding.memory_context ?? []).map(c => <p key={c.memory_id} className="mt-2 rounded-lg bg-[#f3f9f5] px-3 py-2 text-xs leading-5 text-[#2c4a3d]">{c.summary}</p>)}{digest && <a href={`https://suiscan.xyz/mainnet/tx/${encodeURIComponent(digest)}`} target="_blank" rel="noreferrer" className="mt-2 inline-flex min-h-11 items-center text-sm font-medium text-[#176b50] underline underline-offset-4">View transaction evidence ↗</a>}</li>})}</ul> : <div className="p-8 text-center sm:p-12"><h2 className="text-xl font-semibold">{established ? 'No unusual movements identified' : 'Not enough history to assess patterns'}</h2><p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-[#5f6c66]">{established ? 'The available history did not produce an outlier under the current rule. This is not a safety guarantee.' : 'TRACE needs at least 10 transactions with interpretable SUI balance changes before it can establish a baseline.'}</p><Link href="/wallet/overview" className="mt-5 inline-flex text-sm font-medium text-[#176b50] underline underline-offset-4">Return to wallet overview</Link></div>}
      </div><p className="mt-5 text-xs leading-5 text-[#6d7972]">Findings come from the latest analysis in this browser. Respond to alerts or label counterparties on the wallet overview; those choices are stored in Walrus Memory.</p>
    </section></main>
}
