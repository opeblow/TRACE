'use client'

import Link from 'next/link'
import { useCallback, useEffect, useState } from 'react'
import SiteHeader from '@/components/SiteHeader'
import { errorMessage, forgetAllMemories, getMemories } from '@/lib/api'
import { shortHash, suiscanTx, walruscanBlob } from '@/lib/types'
import { getWorkspace, setWorkspace } from '@/lib/workspace'

type Memory = Awaited<ReturnType<typeof getMemories>>['memories'][number]
type Load = { phase: 'loading' } | { phase: 'error'; message: string } | { phase: 'ready'; memories: Memory[]; namespaceRef: string }

const TYPE_LABEL: Record<string, string> = { counterparty_label: 'Counterparty label', alert_feedback: 'Alert feedback', investigation_summary: 'Investigation note' }
const date = (value: string) => { const d = new Date(value); return Number.isNaN(d.getTime()) ? value : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(d) }

function describe(m: Memory) {
  if (m.memory_type === 'counterparty_label') return m.value ? <>Counterparty <span className="font-mono">{shortHash(m.subject)}</span> is “{m.value}”</> : <>Removed the label for <span className="font-mono">{shortHash(m.subject)}</span></>
  if (m.memory_type === 'alert_feedback') return <>Alert on <a className="font-mono text-[#176b50] underline underline-offset-4" href={suiscanTx(m.subject)} target="_blank" rel="noreferrer">{shortHash(m.subject, 6, 4)}</a> marked {m.value.replace('_', ' ')}</>
  return <>{m.value}</>
}

export default function MemoriesPage() {
  const [load, setLoad] = useState<Load>({ phase: 'loading' })
  const [workspace, setWs] = useState<string | null>(null)
  const [reveal, setReveal] = useState(false)
  const [importValue, setImportValue] = useState('')
  const [notice, setNotice] = useState('')
  const [confirmText, setConfirmText] = useState('')
  const [deleting, setDeleting] = useState(false)

  const refresh = useCallback(async () => {
    setLoad({ phase: 'loading' })
    try {
      const data = await getMemories()
      setLoad({ phase: 'ready', memories: data.memories, namespaceRef: data.namespace_ref })
    } catch (err) {
      setLoad({ phase: 'error', message: errorMessage(err, 'TRACE could not reach Walrus Memory. Nothing has been changed.') })
    }
  }, [])

  useEffect(() => { setWs(getWorkspace()); refresh() }, [refresh])

  const copyKey = async () => {
    if (!workspace) return
    try { await navigator.clipboard.writeText(workspace); setNotice('Workspace key copied. Treat it like a password: anyone with it can read and change this workspace’s memory.') }
    catch { setNotice('Copy failed. Reveal the key and copy it manually.') }
  }
  const useOtherKey = () => {
    if (!setWorkspace(importValue)) { setNotice('That is not a valid workspace key (22–64 letters, digits, - or _).'); return }
    setWs(importValue.trim()); setImportValue(''); setNotice('Switched workspace. Memories below now come from that workspace.'); refresh()
  }
  const forget = async () => {
    if (confirmText !== 'DELETE' || deleting) return
    setDeleting(true)
    try { const r = await forgetAllMemories(); setNotice(`${r.deleted} ${r.deleted === 1 ? 'memory' : 'memories'} removed. ${r.message}`); setConfirmText(''); refresh() }
    catch (err) { setNotice(errorMessage(err, 'Deletion failed. Your memories were not changed.')) }
    finally { setDeleting(false) }
  }

  return <main className="min-h-screen"><SiteHeader current="/memories" />
    <section className="mx-auto max-w-6xl px-5 py-12 sm:px-8 sm:py-16">
      <p className="text-xs font-semibold tracking-[.14em] text-[#176b50]">USER-CONTROLLED CONTEXT</p>
      <h1 className="mt-3 text-4xl font-semibold tracking-[-.05em]">Memory Centre</h1>
      <p className="mt-3 max-w-2xl leading-7 text-[#5f6c66]">Labels and alert feedback you confirm are stored encrypted in Walrus Memory and recalled in later sessions to add context to new analyses. They are your assertions and are never treated as proof that activity is safe.</p>
      {notice && <p role="status" className="mt-6 rounded-lg border border-[#dce4de] bg-white px-4 py-3 text-sm text-[#40564b]">{notice}</p>}

      <div className="mt-8 grid gap-5 lg:grid-cols-[1.6fr_1fr]">
        <section aria-labelledby="mem-list" className="overflow-hidden rounded-2xl border border-[#dce4de] bg-white">
          <div className="flex items-center justify-between border-b border-[#e8ede9] px-5 py-4 sm:px-6">
            <div><h2 id="mem-list" className="font-semibold tracking-[-.02em]">Saved memories</h2><p className="mt-1 text-xs text-[#5f6c66]">{load.phase === 'ready' ? `${load.memories.length} records · workspace ref ${load.namespaceRef} · Walrus Mainnet relayer` : 'Recalled from Walrus Memory'}</p></div>
            <button type="button" onClick={refresh} className="rounded-lg border border-[#cbd7ce] px-4 py-2 text-sm font-medium sm:px-3 sm:py-1.5 sm:text-xs hover:bg-[#f3f5f1]">Refresh</button>
          </div>
          {load.phase === 'loading' && <div role="status" aria-label="Loading memories" className="space-y-3 p-5 sm:p-6">{[0, 1, 2].map(i => <div key={i} className="h-12 animate-pulse rounded-lg bg-[#f3f5f1] motion-reduce:animate-none" />)}</div>}
          {load.phase === 'error' && <div role="alert" className="p-6 text-sm text-[#8d3d25]"><p>{load.message}</p><button type="button" onClick={refresh} className="mt-3 rounded-lg border border-[#cbd7ce] px-4 py-2 text-sm font-medium sm:px-3 sm:py-1.5 sm:text-xs text-[#17231f]">Try again</button></div>}
          {load.phase === 'ready' && (load.memories.length === 0
            ? <div className="p-8 text-center"><h3 className="font-medium">No memories in this workspace</h3><p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[#5f6c66]">Analyze a wallet, then label a counterparty or respond to an alert. TRACE only remembers what you explicitly confirm.</p><Link href="/analyze" className="mt-5 inline-flex rounded-lg bg-[#176b50] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#10533d]">Analyze a wallet</Link></div>
            : <ul className="divide-y divide-[#e8ede9]">{load.memories.map(m => (
                <li key={m.memory_id} className="px-5 py-4 sm:px-6">
                  <div className="flex flex-wrap items-center gap-2"><span className="rounded-md bg-[#eaf2ed] px-2 py-0.5 text-xs font-medium text-[#176b50]">{TYPE_LABEL[m.memory_type] ?? m.memory_type}</span><span className="text-xs text-[#5f6c66]">{date(m.created_at)}</span></div>
                  <p className="mt-2 text-sm">{describe(m)}</p>
                  {m.reason && <p className="mt-1 text-xs text-[#5f6c66]">Reason: {m.reason}</p>}
                  <p className="mt-2 text-xs text-[#6d7972]">Wallet <span className="font-mono">{shortHash(m.wallet)}</span> · source: you confirmed it · not independently verified · <a className="underline underline-offset-4" href={walruscanBlob(m.memory_id)} target="_blank" rel="noreferrer">Walrus blob {shortHash(m.memory_id, 6, 4)}</a></p>
                </li>))}</ul>)}
        </section>

        <div className="space-y-5">
          <section aria-labelledby="ws-heading" className="rounded-2xl border border-[#dce4de] bg-white p-5 sm:p-6">
            <h2 id="ws-heading" className="font-semibold tracking-[-.02em]">Your workspace</h2>
            <p className="mt-2 text-sm leading-6 text-[#5f6c66]">There are no accounts in this demo. A random key in this browser scopes your memory; the server stores only a one-way hash of it as the Walrus namespace. Use the same key on another device to recall the same memories.</p>
            <p className="mt-3 break-all rounded-lg bg-[#fafaf7] px-3 py-2 font-mono text-xs">{workspace ? (reveal ? workspace : `${workspace.slice(0, 4)}${'•'.repeat(16)}`) : 'Browser storage unavailable: memory is disabled'}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <button type="button" onClick={() => setReveal(!reveal)} disabled={!workspace} className="rounded-lg border border-[#cbd7ce] px-4 py-2 text-sm font-medium sm:px-3 sm:py-1.5 sm:text-xs hover:bg-[#f3f5f1]">{reveal ? 'Hide' : 'Reveal'}</button>
              <button type="button" onClick={copyKey} disabled={!workspace} className="rounded-lg border border-[#cbd7ce] px-4 py-2 text-sm font-medium sm:px-3 sm:py-1.5 sm:text-xs hover:bg-[#f3f5f1]">Copy key</button>
            </div>
            <label htmlFor="import-ws" className="mt-4 block text-xs font-medium">Use a workspace key from another device</label>
            <div className="mt-1 flex gap-2"><input id="import-ws" value={importValue} onChange={e => setImportValue(e.target.value)} autoComplete="off" spellCheck={false} className="min-w-0 flex-1 rounded-lg border border-[#cbd7ce] px-3 py-2 font-mono text-base focus:border-[#176b50] sm:text-xs focus:outline-none focus:ring-2 focus:ring-[#176b50]/15" /><button type="button" onClick={useOtherKey} disabled={!importValue.trim()} className="rounded-lg bg-[#176b50] px-4 py-2 text-sm font-semibold text-white disabled:bg-[#a9bbb0] sm:text-xs">Switch</button></div>
          </section>

          <section aria-labelledby="del-heading" className="rounded-2xl border border-[#efc9c0] bg-white p-5 sm:p-6">
            <h2 id="del-heading" className="font-semibold tracking-[-.02em]">Delete all memories</h2>
            <p className="mt-2 text-sm leading-6 text-[#5f6c66]">Removes every memory in this workspace from TRACE’s Walrus Memory index, so it will no longer be recalled. Encrypted blobs already written to Walrus are not erased by this action, and public blockchain records are never affected.</p>
            <label htmlFor="confirm-del" className="mt-3 block text-xs font-medium">Type DELETE to confirm</label>
            <div className="mt-1 flex gap-2"><input id="confirm-del" value={confirmText} onChange={e => setConfirmText(e.target.value)} autoComplete="off" className="min-w-0 flex-1 rounded-lg border border-[#cbd7ce] px-3 py-2 text-base focus:border-[#9a3412] sm:text-sm focus:outline-none focus:ring-2 focus:ring-[#9a3412]/15" /><button type="button" onClick={forget} disabled={confirmText !== 'DELETE' || deleting} aria-busy={deleting} className="rounded-lg bg-[#9a3412] px-4 py-2 text-sm font-semibold text-white disabled:bg-[#d8b4a8] sm:text-xs">{deleting ? 'Deleting…' : 'Delete'}</button></div>
          </section>
        </div>
      </div>
      <p className="mt-6 text-xs leading-5 text-[#6d7972]">Never store seed phrases, private keys, or passwords. TRACE rejects text that looks like one.</p>
    </section></main>
}
