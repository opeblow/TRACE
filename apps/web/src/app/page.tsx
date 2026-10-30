import Link from 'next/link'
import HeroAddressForm from '@/components/landing/HeroAddressForm'

/*
  Landing page. Everything shown here describes behaviour the product really has:
  rule names, thresholds and limits come from apps/api/app/services/anomaly.py and learning.py.
  The product preview is labelled as an example and uses placeholder hashes, not real wallets.
*/

const Arrow = ({ className = 'h-4 w-4' }: { className?: string }) => (
  <svg aria-hidden="true" viewBox="0 0 20 20" fill="none" className={className}><path d="M4 10h12m-5-5 5 5-5 5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" /></svg>
)
const Check = () => (
  <svg aria-hidden="true" viewBox="0 0 20 20" fill="none" className="mt-0.5 h-4 w-4 shrink-0"><path d="m5 10.5 3 3 7-7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>
)
const Cross = () => (
  <svg aria-hidden="true" viewBox="0 0 20 20" fill="none" className="mt-0.5 h-4 w-4 shrink-0"><path d="m6 6 8 8m0-8-8 8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>
)
const Eyebrow = ({ children, dark }: { children: React.ReactNode; dark?: boolean }) => (
  <p className={`font-mono text-[11px] font-medium uppercase tracking-[.18em] ${dark ? 'text-[#9fe3c4]' : 'text-[#176b50]'}`}>{children}</p>
)

function Logo({ dark }: { dark?: boolean }) {
  return (
    <span className="flex items-center gap-2.5">
      <span className={`relative grid h-8 w-8 place-items-center overflow-hidden rounded-[10px] ${dark ? 'bg-[#9fe3c4] text-[#0b1f17]' : 'bg-[#176b50] text-white'}`}>
        <svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4" fill="none"><path d="M3 15c3 0 3-6 6-6s3 9 6 9 3-12 6-12" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" /></svg>
      </span>
      <span className={`text-[17px] font-semibold tracking-[-.04em] ${dark ? 'text-white' : ''}`}>TRACE</span>
    </span>
  )
}

/* ---------- Hero product preview (illustrative) ---------- */

function DistributionChart() {
  // Shape of a wallet's outgoing amounts: a typical cluster, a 6×MAD threshold, one point beyond it.
  const bars = [6, 14, 26, 38, 44, 36, 24, 15, 9, 6, 4, 3, 2, 1, 1, 0, 0, 0, 0, 0]
  return (
    <svg viewBox="0 0 320 96" className="h-24 w-full" role="img" aria-label="Example distribution: most transfers cluster together, one sits beyond the threshold">
      {bars.map((h, i) => <rect key={i} x={8 + i * 14} y={84 - h * 1.6} width="9" height={Math.max(h * 1.6, 1)} rx="2" fill={i < 4 || i > 7 ? '#cfe3d6' : '#8cc5a9'} />)}
      <line x1="226" x2="226" y1="6" y2="88" stroke="#176b50" strokeDasharray="3 3" strokeWidth="1.2" />
      <text x="222" y="14" textAnchor="end" className="fill-[#176b50] font-mono" fontSize="8.5">6×MAD threshold</text>
      <circle cx="292" cy="78" r="5" fill="#d9822b" />
      <circle cx="292" cy="78" r="10" fill="none" stroke="#d9822b" strokeOpacity=".35" />
      <line x1="0" x2="320" y1="88" y2="88" stroke="#dce4de" />
    </svg>
  )
}

function ProductPreview() {
  return (
    <div className="relative mx-auto w-full max-w-[560px] anim-rise" style={{ animationDelay: '.15s' }}>
      <div aria-hidden="true" className="absolute -inset-10 -z-10 rounded-[48px] bg-[radial-gradient(closest-side,rgba(23,107,80,.18),transparent)] blur-2xl" />
      <figure className="overflow-hidden rounded-[22px] border border-[#d3ddd6] bg-white shadow-[0_1px_0_rgba(255,255,255,.8)_inset,0_40px_80px_-40px_rgba(16,83,61,.45),0_12px_24px_-16px_rgba(23,35,31,.2)]">
        <div className="flex items-center gap-2 border-b border-[#e8ede9] bg-[#fafaf7] px-4 py-3">
          <span className="h-2.5 w-2.5 rounded-full bg-[#e2e7e3]" /><span className="h-2.5 w-2.5 rounded-full bg-[#e2e7e3]" /><span className="h-2.5 w-2.5 rounded-full bg-[#e2e7e3]" />
          <span className="ml-3 truncate font-mono text-[11px] text-[#6d7972]">trace / wallet / 0x7a3f…c91e</span>
          <span className="ml-auto rounded-full bg-[#fdf3e7] px-2 py-0.5 font-mono text-[10px] font-medium uppercase tracking-wider text-[#9a5a17]">Example</span>
        </div>
        <div className="p-5 sm:p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="font-mono text-[10.5px] uppercase tracking-[.14em] text-[#6d7972]">Finding · outgoing</p>
              <p className="mt-1.5 text-[17px] font-semibold tracking-[-.02em]">Unusual SUI movement</p>
              <p className="mt-1 text-sm text-[#5f6c66]">Beyond the threshold set by this wallet&apos;s own history.</p>
            </div>
            <div className="text-right">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-[#f0d9bd] bg-[#fff8ee] px-2.5 py-1 text-xs font-semibold text-[#9a5a17]">
                <span className="h-1.5 w-1.5 rounded-full bg-[#d9822b]" />Medium
              </span>
              <p className="mt-1.5 font-mono text-[10.5px] text-[#89948e] line-through">High</p>
            </div>
          </div>
          <div className="mt-4 rounded-xl border border-[#eef2ef] bg-[#fbfcfb] px-3 pb-2 pt-3"><DistributionChart /></div>
          <dl className="mt-4 grid grid-cols-3 gap-px overflow-hidden rounded-xl border border-[#eef2ef] bg-[#eef2ef] text-xs">
            {[['Rule', 'amount-outlier-v2'], ['Baseline', 'median + MAD'], ['Evidence', 'Suiscan ↗']].map(([k, v]) => (
              <div key={k} className="bg-white px-3 py-2.5"><dt className="text-[#6d7972]">{k}</dt><dd className="mt-0.5 truncate font-mono text-[11.5px] text-[#17231f]">{v}</dd></div>
            ))}
          </dl>
          <div className="mt-4 rounded-xl border border-[#b9d7c6] bg-[#f3f9f5] p-3.5">
            <p className="flex items-center gap-2 text-[13px] font-semibold text-[#14523d]">
              <span className="grid h-5 w-5 place-items-center rounded-md bg-[#176b50] text-white"><svg aria-hidden="true" viewBox="0 0 20 20" className="h-3 w-3" fill="none"><path d="M10 3v14M3 10h14" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" /></svg></span>
              Memory changed this: high → medium
            </p>
            <p className="mt-1.5 text-[12.5px] leading-5 text-[#2f5c4a]">You labelled the counterparty <span className="font-medium">“My exchange deposit”</span>. Your assertion, not independent verification.</p>
            <p className="mt-2 truncate font-mono text-[10.5px] text-[#5f7d70]">memory-context-v1 · Walrus blob 2nBq…Xk4w</p>
          </div>
        </div>
      </figure>

      <div aria-hidden="true" className="absolute -left-8 -top-5 hidden rounded-xl border border-[#d3ddd6] bg-white/95 px-3 py-2 shadow-[0_16px_32px_-20px_rgba(23,35,31,.4)] backdrop-blur anim-float lg:block">
        <p className="font-mono text-[10px] uppercase tracking-wider text-[#6d7972]">Source</p>
        <p className="text-xs font-semibold">Tatum · Sui Mainnet</p>
      </div>
      <div aria-hidden="true" className="absolute -bottom-5 -right-6 hidden rounded-xl border border-[#d3ddd6] bg-white/95 px-3 py-2 shadow-[0_16px_32px_-20px_rgba(23,35,31,.4)] backdrop-blur anim-float lg:block" style={{ animationDelay: '-3s' }}>
        <p className="font-mono text-[10px] uppercase tracking-wider text-[#6d7972]">Access</p>
        <p className="text-xs font-semibold">Read-only · no signing</p>
      </div>
    </div>
  )
}

/* ---------- Bento visuals ---------- */

function ThinHistoryMeter() {
  return (
    <div className="mt-6 rounded-xl border border-[#e8ede9] bg-[#fbfcfb] p-4">
      <div className="flex items-center justify-between text-xs"><span className="font-medium">Baseline samples</span><span className="font-mono text-[#9a5a17]">4 / 10</span></div>
      <div className="mt-2.5 grid grid-cols-10 gap-1">
        {Array.from({ length: 10 }, (_, i) => <span key={i} className={`h-2 rounded-full ${i < 4 ? 'bg-[#d9822b]' : 'bg-[#eceee9]'}`} />)}
      </div>
      <p className="mt-3 text-xs leading-5 text-[#5f6c66]">History too thin to support a conclusion. TRACE says so instead of guessing.</p>
    </div>
  )
}

function CompareToggle() {
  return (
    <div className="mt-6 space-y-2.5">
      <div className="inline-flex rounded-lg border border-[#dce4de] bg-[#f3f5f1] p-1 text-xs font-medium">
        <span className="rounded-md bg-white px-3 py-1.5 shadow-sm">With memory</span>
        <span className="px-3 py-1.5 text-[#6d7972]">Without memory</span>
      </div>
      <div className="flex items-center gap-3 rounded-lg border border-[#e8ede9] bg-white px-3 py-2.5 text-xs">
        <span className="font-mono text-[#6d7972]">0x91c4…07ab</span>
        <span className="ml-auto text-[#89948e] line-through">High</span>
        <Arrow className="h-3 w-3 text-[#89948e]" />
        <span className="rounded-full bg-[#fff8ee] px-2 py-0.5 font-semibold text-[#9a5a17]">Medium</span>
      </div>
    </div>
  )
}

function BaselineChips() {
  return (
    <div className="mt-6 flex flex-wrap gap-2 text-xs">
      {[['x̃', 'Median', 'typical movement'], ['σ̃', 'MAD', 'typical spread'], ['≥', 'Threshold', 'median + 6×MAD']].map(([g, t, s]) => (
        <span key={t} className="inline-flex items-center gap-2 rounded-full border border-[#dce4de] bg-white py-1.5 pl-1.5 pr-3">
          <span className="grid h-5 w-5 place-items-center rounded-full bg-[#eaf2ed] font-mono text-[11px] text-[#176b50]">{g}</span>
          <span className="font-medium">{t}</span><span className="text-[#89948e]">{s}</span>
        </span>
      ))}
    </div>
  )
}

/* ---------- Page ---------- */

const FAQ: [string, string][] = [
  ['Do I need to connect my wallet?', 'No. TRACE only needs a public Sui address. It never asks for a seed phrase or private key, never requests a signature, and cannot move funds.'],
  ['What makes a transaction “unusual”?', 'TRACE compares each transfer with this wallet’s own history using a median and median-absolute-deviation baseline (rule amount-outlier-v2), with separate baselines for incoming and outgoing transfers and gas-only transactions left out. With fewer than 10 comparable transfers in a direction it reports that the history is too thin rather than flagging anything.'],
  ['Does a finding mean a wallet is malicious?', 'No. A finding means “unusual relative to this wallet’s history” and is a reason to look closer. TRACE never labels activity as a scam, and a large amount on its own is not evidence of wrongdoing.'],
  ['Where is my memory stored, and who can read it?', 'Labels and alert feedback are encrypted and stored through Walrus Memory in a namespace derived from a random workspace key held in your browser. The API never stores that key. Memory is your assertion, never proof that a counterparty is safe.'],
  ['Can I delete what TRACE remembers?', 'Yes. The Memory Centre removes your memories from the workspace index. Walrus blobs are content-addressed, so TRACE explains plainly what removal does and does not erase before you confirm.'],
  ['How much history does TRACE read?', 'The most recent transactions returned by Tatum’s Sui Mainnet interface. When more history exists than was read, the result is marked as partial so you never mistake a sample for the whole picture.'],
]

export default function HomePage() {
  return (
    <div className="min-h-screen overflow-x-clip">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-white focus:px-4 focus:py-2 focus:shadow">Skip to content</a>

      {/* Nav */}
      <header className="sticky top-0 z-40 border-b border-[#dce4de]/70 bg-[#fafaf7]/80 backdrop-blur-xl supports-[backdrop-filter]:bg-[#fafaf7]/65">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-8">
          <Link href="/" aria-label="TRACE home" className="flex min-h-11 items-center"><Logo /></Link>
          <nav aria-label="Main navigation" className="flex items-center gap-1 text-sm text-[#5f6c66] sm:gap-2">
            <a className="hidden min-h-11 items-center rounded-md px-3 transition-colors hover:text-[#17231f] md:inline-flex" href="#product">Product</a>
            <a className="hidden min-h-11 items-center rounded-md px-3 transition-colors hover:text-[#17231f] md:inline-flex" href="#memory">Memory</a>
            <a className="hidden min-h-11 items-center rounded-md px-3 transition-colors hover:text-[#17231f] md:inline-flex" href="#principles">Principles</a>
            <a className="hidden min-h-11 items-center rounded-md px-3 transition-colors hover:text-[#17231f] md:inline-flex" href="#faq">FAQ</a>
            <Link href="/analyze" className="ml-2 inline-flex min-h-10 items-center gap-2 rounded-full bg-[#17231f] px-4 text-[13px] font-medium text-white transition-colors hover:bg-[#176b50]">Open TRACE <Arrow className="h-3.5 w-3.5" /></Link>
          </nav>
        </div>
      </header>

      <main id="main">
        {/* Hero */}
        <section className="relative">
          <div aria-hidden="true" className="bg-grid pointer-events-none absolute inset-0 -z-10" />
          <div aria-hidden="true" className="pointer-events-none absolute left-1/2 top-[-240px] -z-10 h-[520px] w-[920px] -translate-x-1/2 rounded-full bg-[radial-gradient(closest-side,rgba(159,227,196,.45),transparent)]" />
          <div className="mx-auto grid max-w-6xl items-center gap-14 px-4 pb-20 pt-14 sm:px-8 sm:pt-20 lg:grid-cols-[1.05fr_1fr] lg:gap-12 lg:pb-28 lg:pt-24">
            <div className="anim-rise">
              <a href="#memory" className="group inline-flex items-center gap-2 rounded-full border border-[#d3ddd6] bg-white/80 py-1 pl-1 pr-3 text-xs text-[#40564b] shadow-sm backdrop-blur transition-colors hover:border-[#b9d7c6]">
                <span className="rounded-full bg-[#eaf2ed] px-2 py-0.5 font-medium text-[#176b50]">New</span>
                Analyses that learn from your labels
                <Arrow className="h-3 w-3 transition-transform group-hover:translate-x-0.5" />
              </a>
              <h1 className="mt-7 text-[clamp(2.6rem,7.2vw,5.4rem)] font-semibold leading-[.98] tracking-[-.055em] text-[#10201a]">
                Understand what <span className="font-serif font-normal italic tracking-[-.02em] text-[#176b50]">changed</span> in your wallet.
              </h1>
              <p className="mt-6 max-w-lg text-[17px] leading-7 text-[#5f6c66] sm:text-lg sm:leading-8">
                TRACE reads Sui Mainnet activity, flags what is unusual <em className="not-italic text-[#17231f]">for this wallet</em>, shows the evidence behind every finding, and remembers what you confirm.
              </p>
              <div className="mt-9"><HeroAddressForm /></div>
              <ul className="mt-5 flex flex-wrap gap-x-5 gap-y-2 text-[13px] text-[#5f6c66]">
                {['Read-only', 'No wallet connection', 'Never asks for a seed phrase'].map(t => (
                  <li key={t} className="flex items-center gap-1.5"><span className="text-[#176b50]"><Check /></span>{t}</li>
                ))}
              </ul>
            </div>
            <ProductPreview />
          </div>
        </section>

        {/* Built on */}
        <section aria-label="Infrastructure" className="border-y border-[#dce4de] bg-white">
          <div className="mx-auto flex max-w-6xl flex-col items-center gap-5 px-4 py-7 sm:px-8 md:flex-row md:justify-between">
            <p className="font-mono text-[11px] uppercase tracking-[.18em] text-[#6d7972]">Built on</p>
            <ul className="flex flex-wrap items-center justify-center gap-x-10 gap-y-3 text-[15px] font-semibold tracking-[-.02em] text-[#40564b]">
              <li className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-[#4da2ff]" />Sui Mainnet</li>
              <li className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-[#6e3cf0]" />Tatum gRPC</li>
              <li className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-[#1f8a70]" />Walrus Memory</li>
              <li className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-[#17231f]" />Open source</li>
            </ul>
          </div>
        </section>

        {/* Product bento */}
        <section id="product" className="scroll-mt-20">
          <div className="mx-auto max-w-6xl px-4 py-20 sm:px-8 sm:py-28">
            <div className="max-w-2xl">
              <Eyebrow>Product</Eyebrow>
              <h2 className="mt-4 text-[clamp(2rem,4.4vw,3.25rem)] font-semibold leading-[1.05] tracking-[-.045em]">Evidence before confidence.</h2>
              <p className="mt-5 text-lg leading-8 text-[#5f6c66]">Wallet explorers show raw transactions. TRACE tells you which ones are unusual for <em>this</em> wallet, why, and how sure it can be.</p>
            </div>

            <div className="mt-14 grid gap-4 md:grid-cols-6">
              <article className="relative overflow-hidden rounded-3xl border border-[#dce4de] bg-white p-6 sm:p-8 md:col-span-4">
                <Eyebrow>01 · Detection</Eyebrow>
                <h3 className="mt-3 text-2xl font-semibold tracking-[-.03em]">Measured against the wallet’s own history.</h3>
                <p className="mt-3 max-w-md text-[15px] leading-7 text-[#5f6c66]">Robust median + MAD baselines, kept separately for incoming and outgoing transfers, with gas-only transactions left out so tiny fees don’t warp what “normal” means.</p>
                <BaselineChips />
              </article>
              <article className="rounded-3xl border border-[#dce4de] bg-white p-6 sm:p-8 md:col-span-2">
                <Eyebrow>02 · Uncertainty</Eyebrow>
                <h3 className="mt-3 text-xl font-semibold tracking-[-.03em]">Honest about thin history.</h3>
                <ThinHistoryMeter />
              </article>
              <article className="rounded-3xl border border-[#dce4de] bg-white p-6 sm:p-8 md:col-span-2">
                <Eyebrow>03 · Provenance</Eyebrow>
                <h3 className="mt-3 text-xl font-semibold tracking-[-.03em]">Every finding cites its source.</h3>
                <ul className="mt-6 space-y-2.5 font-mono text-[12px]">
                  {[['tx', '9WkP…r2Lm ↗'], ['rule', 'amount-outlier-v2'], ['data', 'Tatum · mainnet']].map(([k, v]) => (
                    <li key={k} className="flex items-center justify-between rounded-lg border border-[#eef2ef] bg-[#fbfcfb] px-3 py-2"><span className="text-[#89948e]">{k}</span><span>{v}</span></li>
                  ))}
                </ul>
              </article>
              <article className="rounded-3xl border border-[#dce4de] bg-white p-6 sm:p-8 md:col-span-2">
                <Eyebrow>04 · Compare</Eyebrow>
                <h3 className="mt-3 text-xl font-semibold tracking-[-.03em]">See exactly what memory changed.</h3>
                <CompareToggle />
              </article>
              <article className="relative overflow-hidden rounded-3xl bg-[#176b50] p-6 text-white sm:p-8 md:col-span-2">
                <div aria-hidden="true" className="bg-grid-dark absolute inset-0" />
                <div className="relative">
                  <Eyebrow dark>05 · Safety</Eyebrow>
                  <h3 className="mt-3 text-xl font-semibold tracking-[-.03em]">Read-only, by design.</h3>
                  <p className="mt-3 text-[14px] leading-6 text-white/75">No wallet connection, no signatures, no custody. TRACE can look. It can’t touch.</p>
                  <Link href="/analyze" className="mt-6 inline-flex min-h-11 items-center gap-2 rounded-full bg-white px-4 text-sm font-medium text-[#10533d] transition-colors hover:bg-[#eaf2ed]">Try it on any address <Arrow className="h-3.5 w-3.5" /></Link>
                </div>
              </article>
            </div>
          </div>
        </section>

        {/* Learning loop (dark) */}
        <section id="memory" className="scroll-mt-16 bg-[#0b1a14] text-white">
          <div className="relative mx-auto max-w-6xl overflow-hidden px-4 py-20 sm:px-8 sm:py-28">
            <div aria-hidden="true" className="bg-grid-dark pointer-events-none absolute inset-0" />
            <div aria-hidden="true" className="pointer-events-none absolute -right-40 top-0 h-[480px] w-[480px] rounded-full bg-[radial-gradient(closest-side,rgba(31,138,112,.35),transparent)]" />
            <div className="relative grid gap-14 lg:grid-cols-[.9fr_1.1fr] lg:items-center">
              <div>
                <Eyebrow dark>Walrus Memory</Eyebrow>
                <h2 className="mt-4 text-[clamp(2rem,4.4vw,3.25rem)] font-semibold leading-[1.05] tracking-[-.045em]">
                  It remembers <span className="font-serif font-normal italic text-[#9fe3c4]">what you confirm</span>, and shows its work.
                </h2>
                <p className="mt-5 max-w-md text-[17px] leading-8 text-white/70">Label a counterparty or mark an alert as expected. TRACE stores it encrypted on Walrus, recalls it next time, and cites the exact memory behind every change.</p>
                <ul className="mt-8 space-y-3 text-[15px] text-white/80">
                  {['Writes confirmed only after the Walrus job completes', 'Recalled records re-validated as untrusted input', 'Your labels are shown as assertions, never verified facts', 'Memory offline? Analysis continues, stateless, and says so'].map(t => (
                    <li key={t} className="flex gap-3"><span className="text-[#9fe3c4]"><Check /></span>{t}</li>
                  ))}
                </ul>
              </div>

              <ol className="relative space-y-3" aria-label="How the learning loop works">
                <span aria-hidden="true" className="absolute bottom-8 left-[27px] top-8 w-px bg-gradient-to-b from-[#9fe3c4]/0 via-[#9fe3c4]/40 to-[#9fe3c4]/0" />
                {[
                  ['Analyze', 'Findings from chain facts alone.', 'outgoing transfer · high'],
                  ['Teach', 'You label the counterparty.', '“My exchange deposit” → pending…'],
                  ['Store', 'Encrypted, uploaded, indexed on Walrus.', 'stored · blob 2nBq…Xk4w'],
                  ['Recall', 'Next analysis cites the memory it used.', 'high → medium · memory-context-v1'],
                ].map(([t, d, code], i) => (
                  <li key={t} className="relative flex gap-5 rounded-2xl border border-white/10 bg-white/[.04] p-4 backdrop-blur-sm transition-colors hover:border-[#9fe3c4]/30 hover:bg-white/[.06] sm:p-5">
                    <span className="relative z-10 grid h-9 w-9 shrink-0 place-items-center rounded-full border border-[#9fe3c4]/40 bg-[#0b1a14] font-mono text-xs text-[#9fe3c4]">0{i + 1}</span>
                    <div className="min-w-0">
                      <p className="font-semibold tracking-[-.01em]">{t}</p>
                      <p className="mt-0.5 text-sm text-white/60">{d}</p>
                      <p className="mt-2.5 truncate rounded-md bg-black/30 px-2.5 py-1.5 font-mono text-[11.5px] text-[#9fe3c4]/90">{code}</p>
                    </div>
                  </li>
                ))}
                <li className="pl-14 font-mono text-[10.5px] uppercase tracking-wider text-white/40">Example values · placeholder hashes</li>
              </ol>
            </div>
          </div>
        </section>

        {/* Principles */}
        <section id="principles" className="scroll-mt-16">
          <div className="mx-auto max-w-6xl px-4 py-20 sm:px-8 sm:py-28">
            <div className="grid gap-12 lg:grid-cols-[1fr_1.2fr]">
              <div>
                <Eyebrow>Principles</Eyebrow>
                <h2 className="mt-4 text-[clamp(2rem,4.4vw,3.25rem)] font-semibold leading-[1.05] tracking-[-.045em]">Careful with words. <span className="text-[#89948e]">Careful with conclusions.</span></h2>
                <p className="mt-5 max-w-md text-lg leading-8 text-[#5f6c66]">An unusual transaction is a reason to look closer. It is not, by itself, proof of anything.</p>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="rounded-3xl border border-[#b9d7c6] bg-[#f3f9f5] p-6">
                  <p className="text-sm font-semibold text-[#14523d]">TRACE will say</p>
                  <ul className="mt-4 space-y-3 text-[14px] leading-6 text-[#2f5c4a]">
                    {['“Unusual relative to this wallet’s history”', '“History too limited to assess”', '“Partial: more history exists”', '“Memory unavailable — stateless result”'].map(t => <li key={t} className="flex gap-2.5"><Check />{t}</li>)}
                  </ul>
                </div>
                <div className="rounded-3xl border border-[#eed2c7] bg-[#fff8f5] p-6">
                  <p className="text-sm font-semibold text-[#8d3d25]">TRACE won’t say</p>
                  <ul className="mt-4 space-y-3 text-[14px] leading-6 text-[#8d3d25]/90">
                    {['“This is a scam”', '“Large amount, therefore malicious”', '“Verified safe” because you labelled it', 'Anything the data can’t support'].map(t => <li key={t} className="flex gap-2.5"><Cross />{t}</li>)}
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* FAQ */}
        <section id="faq" className="scroll-mt-16 border-t border-[#dce4de] bg-white">
          <div className="mx-auto grid max-w-6xl gap-10 px-4 py-20 sm:px-8 sm:py-28 lg:grid-cols-[1fr_1.6fr]">
            <div>
              <Eyebrow>FAQ</Eyebrow>
              <h2 className="mt-4 text-[clamp(2rem,4.4vw,3rem)] font-semibold leading-[1.05] tracking-[-.045em]">Questions, answered plainly.</h2>
            </div>
            <div className="divide-y divide-[#e8ede9] border-y border-[#e8ede9]">
              {FAQ.map(([q, a]) => (
                <details key={q} className="faq group">
                  <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-6 py-5 text-[16px] font-medium tracking-[-.01em] transition-colors hover:text-[#176b50]">
                    {q}
                    <span aria-hidden="true" className="faq-icon grid h-7 w-7 shrink-0 place-items-center rounded-full border border-[#dce4de] text-[#5f6c66] transition-transform duration-200">
                      <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none"><path d="M10 4v12M4 10h12" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>
                    </span>
                  </summary>
                  <p className="max-w-2xl pb-6 pr-10 text-[15px] leading-7 text-[#5f6c66]">{a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        {/* Final CTA */}
        <section className="px-4 pb-6 pt-6 sm:px-8">
          <div className="relative mx-auto max-w-6xl overflow-hidden rounded-[32px] bg-[#0b1a14] px-6 py-16 text-center text-white sm:px-12 sm:py-24">
            <div aria-hidden="true" className="bg-grid-dark pointer-events-none absolute inset-0" />
            <div aria-hidden="true" className="pointer-events-none absolute left-1/2 top-full h-[420px] w-[820px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[radial-gradient(closest-side,rgba(159,227,196,.35),transparent)]" />
            <div className="relative mx-auto flex max-w-2xl flex-col items-center">
              <h2 className="text-[clamp(2.2rem,5.5vw,4rem)] font-semibold leading-[1] tracking-[-.05em]">See your wallet <span className="font-serif font-normal italic text-[#9fe3c4]">clearly.</span></h2>
              <p className="mt-5 max-w-md text-[17px] leading-7 text-white/65">Paste any public Sui address. No sign-up, no wallet connection.</p>
              <div className="mt-9 w-full max-w-xl text-left"><HeroAddressForm tone="dark" /></div>
            </div>
          </div>
        </section>
      </main>

      <footer>
        <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-10 text-sm text-[#5f6c66] sm:px-8 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-4"><Logo /><span className="hidden h-4 w-px bg-[#dce4de] sm:block" /><span className="hidden sm:inline">Sui wallet intelligence · Read-only analysis</span></div>
          <nav aria-label="Footer" className="flex flex-wrap gap-x-6 gap-y-2">
            <Link href="/analyze" className="hover:text-[#17231f]">Analyze</Link>
            <Link href="/alerts" className="hover:text-[#17231f]">Insights</Link>
            <Link href="/memories" className="hover:text-[#17231f]">Memory Centre</Link>
            <a href="https://github.com/opeblow/TRACE" className="hover:text-[#17231f]" rel="noreferrer" target="_blank">GitHub</a>
          </nav>
        </div>
        <p className="mx-auto max-w-6xl px-4 pb-10 text-xs leading-5 text-[#89948e] sm:px-8">TRACE does not custody assets, sign transactions, or guarantee that a wallet is safe. Findings describe observable patterns and are not financial or legal advice.</p>
      </footer>
    </div>
  )
}
