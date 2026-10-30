'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'

const validSuiAddress = (value: string) => /^0x[a-fA-F0-9]{64}$/.test(value.trim())

/** Hero address field. Validates locally, then hands off to /analyze, which runs the real analysis. */
export default function HeroAddressForm({ tone = 'light' }: { tone?: 'light' | 'dark' }) {
  const router = useRouter()
  const [address, setAddress] = useState('')
  const [touched, setTouched] = useState(false)
  const invalid = touched && address.length > 0 && !validSuiAddress(address)
  const dark = tone === 'dark'
  const id = `hero-address-${tone}`

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    setTouched(true)
    if (!validSuiAddress(address)) return
    router.push(`/analyze?address=${encodeURIComponent(address.trim())}`)
  }

  return (
    <form onSubmit={submit} noValidate className="w-full max-w-xl">
      <label htmlFor={id} className="sr-only">Sui wallet address</label>
      <div className={`group flex flex-col gap-2 rounded-2xl border p-2 transition-shadow focus-within:shadow-[0_0_0_4px_rgba(23,107,80,.14)] sm:flex-row sm:items-center ${dark ? 'border-white/15 bg-white/[.06]' : 'border-[#d3ddd6] bg-white shadow-[0_1px_2px_rgba(23,35,31,.06),0_12px_32px_-20px_rgba(23,35,31,.35)]'}`}>
        <input
          id={id}
          type="text"
          inputMode="text"
          autoComplete="off"
          spellCheck={false}
          value={address}
          onChange={e => setAddress(e.target.value)}
          onBlur={() => setTouched(true)}
          placeholder="Paste a Sui address (0x…)"
          aria-invalid={invalid}
          aria-describedby={invalid ? `${id}-error` : undefined}
          className={`min-w-0 flex-1 bg-transparent px-3 py-3 font-mono text-base outline-none placeholder:font-sans sm:text-sm ${dark ? 'text-white placeholder:text-white/45' : 'text-[#17231f] placeholder:text-[#89948e]'}`}
        />
        <button type="submit" className={`inline-flex shrink-0 items-center justify-center gap-2 rounded-xl px-5 py-3 text-sm font-semibold transition-colors ${dark ? 'bg-[#9fe3c4] text-[#0b1f17] hover:bg-[#b9ecd4]' : 'bg-[#176b50] text-white hover:bg-[#10533d]'}`}>
          Analyze wallet
          <svg aria-hidden="true" viewBox="0 0 20 20" fill="none" className="h-4 w-4"><path d="M4 10h12m-5-5 5 5-5 5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" /></svg>
        </button>
      </div>
      {invalid && <p id={`${id}-error`} role="alert" className={`mt-2 text-sm ${dark ? 'text-[#ffc9b3]' : 'text-[#9b4c25]'}`}>Enter 0x followed by 64 hexadecimal characters.</p>}
    </form>
  )
}
