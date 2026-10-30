'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import SiteHeader from '@/components/SiteHeader'
import { analyzeWallet, listInvestigations, type InvestigationSummary } from '@/lib/api'
import { RESULT_KEY } from '@/lib/types'

const validSuiAddress = (value: string) => /^0x[a-fA-F0-9]{64}$/.test(value.trim())

export default function AnalyzePage() {
  const router = useRouter()
  const [address, setAddress] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [touched, setTouched] = useState(false)
  const invalid = touched && address.length > 0 && !validSuiAddress(address)

  const [history, setHistory] = useState<{ state: 'loading' | 'ready' | 'error'; items: InvestigationSummary[]; durable: boolean }>({ state: 'loading', items: [], durable: false })
  useEffect(() => {
    listInvestigations()
      .then(data => setHistory({ state: 'ready', items: data.investigations, durable: data.durable }))
      .catch(() => setHistory({ state: 'error', items: [], durable: false }))
  }, [])

  // Prefill from the landing-page form (?address=0x…). The user still confirms by submitting.
  useEffect(() => {
    const fromQuery = new URLSearchParams(window.location.search).get('address')
    if (fromQuery) { setAddress(fromQuery.trim()); setTouched(true) }
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setTouched(true)
    if (!validSuiAddress(address) || loading) return
    setLoading(true)
    setError('')
    try {
      const result = await analyzeWallet(address.trim())
      try { localStorage.setItem(RESULT_KEY, JSON.stringify(result)) } catch { /* storage blocked */ }
      router.push('/wallet/overview')
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'We could not retrieve this wallet. Check the address and try again.')
    } finally {
      setLoading(false)
    }
  }

  return <main className="min-h-screen">
    <SiteHeader current="/analyze" />
    <section className="mx-auto max-w-5xl px-5 py-12 sm:px-8 sm:py-20"><div className="max-w-2xl"><p className="text-xs font-semibold tracking-[.14em] text-[#176b50]">SUI WALLET ANALYSIS</p><h1 className="mt-4 text-4xl font-semibold tracking-[-.05em] sm:text-5xl">Start with an address.</h1><p className="mt-5 text-lg leading-8 text-[#5f6c66]">Review observable activity and evidence for a Sui wallet. TRACE only needs the public address.</p></div>
      <form onSubmit={handleSubmit} className="mt-10 max-w-2xl rounded-2xl border border-[#dce4de] bg-white p-5 shadow-[0_16px_48px_-36px_rgba(23,35,31,.35)] sm:p-7" noValidate>
        <label htmlFor="address" className="block text-sm font-semibold">Sui wallet address</label>
        <div className="mt-2 flex flex-col gap-3 sm:flex-row"><input id="address" name="address" type="text" autoComplete="off" spellCheck={false} value={address} onBlur={() => setTouched(true)} onChange={e => { setAddress(e.target.value); setError('') }} placeholder="0x followed by 64 hexadecimal characters" aria-invalid={invalid || !!error} aria-describedby={['address-help', invalid ? 'address-invalid' : '', error ? 'address-error' : ''].filter(Boolean).join(' ')} className="min-w-0 flex-1 rounded-lg border border-[#cbd7ce] bg-white px-4 py-3 text-base font-mono placeholder:font-sans sm:text-sm placeholder:text-[#89948e] focus:border-[#176b50] focus:outline-none focus:ring-2 focus:ring-[#176b50]/15"/><button type="submit" aria-busy={loading} disabled={loading || !validSuiAddress(address)} className="rounded-lg bg-[#176b50] px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-[#10533d] disabled:cursor-not-allowed disabled:bg-[#a9bbb0]">{loading ? 'Retrieving activity…' : 'Analyze wallet'}</button></div>
        <p id="address-help" className="mt-3 text-sm leading-6 text-[#5f6c66]">Sui addresses are 32-byte hexadecimal values. Wallet addresses and on-chain activity are public.</p>
        {invalid && <p id="address-invalid" role="alert" className="mt-2 text-sm text-[#9b4c25]">Enter a valid Sui address: 0x followed by 64 hexadecimal characters.</p>}
        {error && <p id="address-error" role="alert" className="mt-3 rounded-lg border border-[#eed2c7] bg-[#fff8f5] px-4 py-3 text-sm text-[#8d3d25]">{error}</p>}
      </form>
      <section aria-labelledby="history-title" className="mt-12 max-w-2xl">
        <div className="flex items-baseline justify-between gap-4"><h2 id="history-title" className="text-lg font-semibold tracking-[-.02em]">Recent investigations</h2>{history.state === 'ready' && history.items.length > 0 && !history.durable && <span className="text-xs text-[#705c32]">Kept until the server restarts</span>}</div>
        {history.state === 'loading' && <p role="status" className="mt-3 text-sm text-[#5f6c66]">Loading your history…</p>}
        {history.state === 'error' && <p role="status" className="mt-3 text-sm text-[#5f6c66]">History is unavailable right now. You can still analyze a wallet.</p>}
        {history.state === 'ready' && history.items.length === 0 && <p className="mt-3 text-sm text-[#5f6c66]">No investigations yet in this workspace. Analyses you run here will be listed.</p>}
        {history.state === 'ready' && history.items.length > 0 && <ul className="mt-3 divide-y divide-[#e8ede9] rounded-xl border border-[#dce4de] bg-white">
          {history.items.map(item => <li key={item.investigation_id}><button type="button" onClick={() => { setAddress(item.address); setTouched(true); window.scrollTo({ top: 0, behavior: 'smooth' }) }} className="flex w-full items-center gap-3 px-4 py-3 text-left text-sm hover:bg-[#fafaf7]">
            <span className="min-w-0 flex-1 truncate font-mono">{item.address.slice(0, 10)}…{item.address.slice(-6)}</span>
            <span className="text-[#5f6c66]">{item.anomaly_count ? `${item.anomaly_count} finding${item.anomaly_count > 1 ? 's' : ''}${item.highest_severity ? ` · ${item.highest_severity}` : ''}` : 'No findings'}</span>
            <time dateTime={item.created_at} className="hidden text-xs text-[#89948e] sm:inline">{new Date(item.created_at).toLocaleDateString()}</time>
          </button></li>)}
        </ul>}
      </section>
      <p className="mt-5 max-w-2xl text-xs leading-5 text-[#6d7972]">Read-only analysis. Never enter a seed phrase or private key. Findings describe observable patterns and are not proof of malicious activity.</p>
    </section>
  </main>
}
