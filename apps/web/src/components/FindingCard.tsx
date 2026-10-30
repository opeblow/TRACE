'use client'

import { useId, useState } from 'react'
import { rememberLabel, submitAlertFeedback } from '@/lib/api'
import { shortHash, suiscanAccount, suiscanTx, walruscanBlob, type Finding } from '@/lib/types'
import { MemoryJobStatus, useMemoryJob } from './MemoryJob'

const SEVERITY_STYLE: Record<string, { label: string; icon: string; className: string }> = {
  high: { label: 'High priority', icon: '▲', className: 'border-[#efc9c0] bg-[#fff4f1] text-[#9a3412]' },
  medium: { label: 'Review', icon: '●', className: 'border-[#e9d9b8] bg-[#fffaf0] text-[#705c32]' },
  low: { label: 'Low priority', icon: '▽', className: 'border-[#dce4de] bg-[#f3f5f1] text-[#40564b]' },
}
const STATE_LABEL: Record<string, string> = {
  marked_expected: 'You marked this expected',
  marked_incorrect: 'You marked this incorrect',
  needs_review: 'You flagged this for review',
}
const FEEDBACK = [
  { value: 'expected', label: 'Expected' },
  { value: 'needs_review', label: 'Needs review' },
  { value: 'incorrect', label: 'Incorrect alert' },
] as const

export function SeverityChip({ severity }: { severity?: string }) {
  const style = SEVERITY_STYLE[severity ?? 'medium'] ?? SEVERITY_STYLE.medium
  return <span className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs font-medium ${style.className}`}><span aria-hidden="true">{style.icon}</span>{style.label}</span>
}

type Props = { finding: Finding; wallet: string; interactive: boolean; onApply: () => void }

export default function FindingCard({ finding, wallet, interactive, onApply }: Props) {
  const [panel, setPanel] = useState<'none' | 'feedback' | 'label'>('none')
  const digest = finding.transaction_digest || finding.evidence?.[0]?.ref
  const contexts = finding.memory_context ?? []
  const changed = finding.severity_without_memory && finding.severity_without_memory !== finding.severity
  const direction = finding.direction === 'out' ? 'Outflow' : finding.direction === 'in' ? 'Inflow' : 'Movement'
  const panelId = useId()

  return (
    <li className="px-5 py-5 sm:px-6">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="font-medium">{direction} of <span className="tabular-nums">{finding.amount_sui}</span> SUI</h3>
        <SeverityChip severity={finding.severity} />
        {finding.state && STATE_LABEL[finding.state] && <span className="rounded-md border border-[#dce4de] bg-white px-2 py-1 text-xs text-[#40564b]">{STATE_LABEL[finding.state]}</span>}
      </div>
      <p className="mt-2 text-sm leading-6 text-[#5f6c66]">{finding.rationale}</p>
      <dl className="mt-3 grid gap-x-6 gap-y-1 text-xs text-[#5f6c66] sm:grid-cols-[auto_1fr]">
        <dt className="font-medium text-[#40564b]">Counterparty</dt>
        <dd>{finding.counterparty ? <a className="font-mono text-[#176b50] underline underline-offset-4" href={suiscanAccount(finding.counterparty)} target="_blank" rel="noreferrer">{shortHash(finding.counterparty)}</a> : 'Not shown in the transaction’s SUI balance changes'}</dd>
        <dt className="font-medium text-[#40564b]">Rule</dt>
        <dd>{finding.rule_version} · threshold {finding.threshold_sui} SUI · uncertainty {finding.uncertainty}</dd>
        {finding.confidence != null && <>
          <dt className="font-medium text-[#40564b]">Confidence</dt>
          <dd>{Math.round(finding.confidence * 100)}%{finding.confidence_factors?.length ? <ul className="mt-0.5 list-disc pl-4">{finding.confidence_factors.map(f => <li key={f}>{f}</li>)}</ul> : null}</dd>
        </>}
        <dt className="font-medium text-[#40564b]">Evidence</dt>
        <dd>{digest ? <a className="font-mono text-[#176b50] underline underline-offset-4" href={suiscanTx(digest)} target="_blank" rel="noreferrer">Open transaction evidence ({shortHash(digest, 6, 4)})</a> : 'No transaction reference was returned.'}</dd>
      </dl>

      {contexts.length > 0 && (
        <div className="mt-4 rounded-xl border border-[#b9d7c6] bg-[#f3f9f5] p-4 text-sm">
          <p className="font-semibold text-[#14523d]">{changed ? <>Memory changed this: {finding.severity_without_memory} → {finding.severity}</> : 'Memory added context'}</p>
          <ul className="mt-2 space-y-2">
            {contexts.map(context => (
              <li key={context.memory_id} className="leading-6 text-[#2c4a3d]">
                {context.summary}
                <span className="block text-xs text-[#5f6c66]">Source: your confirmed {context.memory_type.replace('_', ' ')} · user assertion, not verified · <a className="underline underline-offset-4" href={walruscanBlob(context.memory_id)} target="_blank" rel="noreferrer">Walrus blob {shortHash(context.memory_id, 6, 4)}</a></span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {interactive && digest && (
        <div className="mt-4">
          <div className="flex flex-wrap gap-2">
            <button type="button" aria-expanded={panel === 'feedback'} aria-controls={`${panelId}-feedback`} onClick={() => setPanel(panel === 'feedback' ? 'none' : 'feedback')} className="min-h-11 flex-1 rounded-lg border border-[#cbd7ce] bg-white px-3 text-sm font-medium hover:bg-[#f3f5f1] sm:min-h-0 sm:flex-none sm:py-2 sm:text-xs">Respond to this alert</button>
            {finding.counterparty && <button type="button" aria-expanded={panel === 'label'} aria-controls={`${panelId}-label`} onClick={() => setPanel(panel === 'label' ? 'none' : 'label')} className="min-h-11 flex-1 rounded-lg border border-[#cbd7ce] bg-white px-3 text-sm font-medium hover:bg-[#f3f5f1] sm:min-h-0 sm:flex-none sm:py-2 sm:text-xs">Label counterparty</button>}
          </div>
          {panel === 'feedback' && <FeedbackForm id={`${panelId}-feedback`} digest={digest} wallet={wallet} onApply={onApply} />}
          {panel === 'label' && finding.counterparty && <LabelForm id={`${panelId}-label`} counterparty={finding.counterparty} wallet={wallet} onApply={onApply} />}
        </div>
      )}
    </li>
  )
}

function ConsentNote() {
  return <p className="mt-2 text-xs leading-5 text-[#6d7972]">Stored encrypted in Walrus Memory for this browser’s workspace. It is your assertion: TRACE uses it as context and never as proof that activity is safe. Never enter a seed phrase, private key, or password.</p>
}

function FeedbackForm({ id, digest, wallet, onApply }: { id: string; digest: string; wallet: string; onApply: () => void }) {
  const [choice, setChoice] = useState<'expected' | 'needs_review' | 'incorrect'>('expected')
  const [reason, setReason] = useState('')
  const [consent, setConsent] = useState(false)
  const job = useMemoryJob()
  return (
    <form id={id} className="mt-3 rounded-xl border border-[#dce4de] bg-[#fafaf7] p-4" onSubmit={e => { e.preventDefault(); if (consent && !job.busy) job.run(() => submitAlertFeedback(digest, wallet, choice, reason)) }}>
      <fieldset>
        <legend className="text-sm font-semibold">How should TRACE treat this alert?</legend>
        <div className="mt-2 flex flex-wrap gap-2">
          {FEEDBACK.map(option => (
            <label key={option.value} className={`inline-flex min-h-11 cursor-pointer items-center rounded-lg border px-4 text-sm font-medium sm:min-h-0 sm:py-2 sm:text-xs has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-[#176b50]/40 ${choice === option.value ? 'border-[#176b50] bg-white text-[#176b50]' : 'border-[#cbd7ce] bg-white'}`}>
              <input type="radio" name={`${id}-choice`} value={option.value} checked={choice === option.value} onChange={() => setChoice(option.value)} className="sr-only" />{option.label}
            </label>
          ))}
        </div>
      </fieldset>
      <label className="mt-3 block text-xs font-medium" htmlFor={`${id}-reason`}>Reason (optional)</label>
      <input id={`${id}-reason`} maxLength={200} value={reason} onChange={e => setReason(e.target.value)} placeholder="e.g. Monthly transfer to my exchange" className="mt-1 w-full rounded-lg border border-[#cbd7ce] bg-white px-3 py-2.5 text-base sm:text-sm focus:border-[#176b50] focus:outline-none focus:ring-2 focus:ring-[#176b50]/15" />
      <label className="mt-3 flex min-h-11 cursor-pointer items-center gap-3 text-sm sm:text-xs"><input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} className="shrink-0 accent-[#176b50]" />Remember this feedback in Walrus Memory</label>
      <ConsentNote />
      <button type="submit" disabled={!consent || job.busy} aria-busy={job.busy} className="mt-3 w-full rounded-lg bg-[#176b50] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#10533d] disabled:cursor-not-allowed disabled:bg-[#a9bbb0] sm:w-auto sm:text-xs">Save feedback</button>
      <MemoryJobStatus state={job.state} onApply={onApply} />
    </form>
  )
}

function LabelForm({ id, counterparty, wallet, onApply }: { id: string; counterparty: string; wallet: string; onApply: () => void }) {
  const [label, setLabel] = useState('')
  const [consent, setConsent] = useState(false)
  const job = useMemoryJob()
  const valid = label.trim().length > 0
  return (
    <form id={id} className="mt-3 rounded-xl border border-[#dce4de] bg-[#fafaf7] p-4" onSubmit={e => { e.preventDefault(); if (consent && valid && !job.busy) job.run(() => rememberLabel(wallet, counterparty, label.trim())) }}>
      <label className="block text-sm font-semibold" htmlFor={`${id}-input`}>Label <span className="font-mono font-normal">{shortHash(counterparty)}</span></label>
      <input id={`${id}-input`} maxLength={60} value={label} onChange={e => setLabel(e.target.value)} placeholder="e.g. My exchange deposit" className="mt-2 w-full rounded-lg border border-[#cbd7ce] bg-white px-3 py-2.5 text-base sm:text-sm focus:border-[#176b50] focus:outline-none focus:ring-2 focus:ring-[#176b50]/15" />
      <label className="mt-3 flex min-h-11 cursor-pointer items-center gap-3 text-sm sm:text-xs"><input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} className="shrink-0 accent-[#176b50]" />Remember this label in Walrus Memory</label>
      <ConsentNote />
      <button type="submit" disabled={!consent || !valid || job.busy} aria-busy={job.busy} className="mt-3 w-full rounded-lg bg-[#176b50] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#10533d] disabled:cursor-not-allowed disabled:bg-[#a9bbb0] sm:w-auto sm:text-xs">Save label</button>
      <MemoryJobStatus state={job.state} onApply={onApply} />
    </form>
  )
}
