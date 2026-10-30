import Link from 'next/link'

const Arrow = () => <svg aria-hidden="true" viewBox="0 0 20 20" fill="none" className="h-4 w-4"><path d="M4 10h12m-5-5 5 5-5 5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>

export default function HomePage() {
  return (
    <main className="min-h-screen">
      <header className="border-b border-[#dce4de]">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-5 sm:px-8">
          <Link href="/" className="flex min-h-11 items-center gap-3" aria-label="TRACE home">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-[#176b50] text-sm font-bold text-white">T</span>
            <span className="text-lg font-semibold tracking-[-0.04em]">TRACE</span>
          </Link>
          <nav aria-label="Main navigation" className="flex items-center gap-5 text-sm text-[#5f6c66] sm:gap-8">
            <Link className="hidden transition-colors hover:text-[#17231f] sm:inline" href="#how-it-works">How it works</Link>
            <Link className="hidden transition-colors hover:text-[#17231f] sm:inline" href="#principles">Principles</Link>
            <Link href="/analyze" className="inline-flex min-h-11 items-center gap-2 rounded-lg bg-[#176b50] px-4 font-medium text-white transition-colors hover:bg-[#10533d]">Open TRACE <Arrow /></Link>
          </nav>
        </div>
      </header>

      <section className="mx-auto grid max-w-6xl gap-14 px-5 pb-20 pt-16 sm:px-8 sm:pt-24 lg:grid-cols-[1.1fr_.9fr] lg:items-center lg:gap-20 lg:pb-28">
        <div>
          <div className="mb-7 inline-flex items-center gap-2 rounded-full border border-[#dce4de] bg-white px-3 py-1.5 text-xs font-medium text-[#40564b]"><span className="h-2 w-2 rounded-full bg-[#176b50]" />SUI WALLET INTELLIGENCE</div>
          <h1 className="max-w-3xl text-5xl font-semibold leading-[1.04] tracking-[-0.055em] sm:text-6xl lg:text-[4.5rem]">Understand what changed in your wallet.</h1>
          <p className="mt-6 max-w-xl text-lg leading-8 text-[#5f6c66]">TRACE turns public Sui activity into a clearer picture of what happened, why it stands out, and what remains uncertain.</p>
          <div className="mt-9 flex flex-col gap-3 sm:flex-row">
            <Link href="/analyze" className="inline-flex items-center justify-center gap-3 rounded-lg bg-[#176b50] px-5 py-3.5 font-medium text-white hover:bg-[#10533d]">Analyze a wallet <Arrow /></Link>
            <a href="#how-it-works" className="inline-flex items-center justify-center rounded-lg border border-[#dce4de] bg-white px-5 py-3.5 font-medium hover:bg-[#f3f5f1]">See how it works</a>
          </div>
          <p className="mt-5 text-sm text-[#5f6c66]">Read-only by default. Never enter a seed phrase or private key.</p>
        </div>
        <aside className="rounded-2xl border border-[#dce4de] bg-white p-6 shadow-[0_16px_48px_-36px_rgba(23,35,31,.35)] sm:p-8" aria-label="How TRACE explains activity">
          <div className="flex items-center justify-between border-b border-[#e8ede9] pb-5"><div><p className="text-xs font-semibold tracking-[.14em] text-[#5f6c66]">A CLEARER VIEW</p><p className="mt-1 font-medium">From activity to understanding</p></div><span className="rounded-md bg-[#eaf2ed] px-2.5 py-1 text-xs font-medium text-[#176b50]">Evidence first</span></div>
          <ol className="mt-6 space-y-5">
            {[
              ['01', 'Start with the facts', 'Review available wallet activity and its source.'],
              ['02', 'See what stands out', 'Understand deviations against the history we can observe.'],
              ['03', 'Know the limits', 'See when the available history is too limited to support a conclusion.'],
            ].map(([n, title, body]) => <li key={n} className="flex gap-4"><span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-[#f3f5f1] text-xs font-semibold text-[#176b50]">{n}</span><div><h2 className="font-medium">{title}</h2><p className="mt-1 text-sm leading-6 text-[#5f6c66]">{body}</p></div></li>)}
          </ol>
          <div className="mt-7 rounded-xl bg-[#fafaf7] p-4 text-sm leading-6 text-[#5f6c66]">An unusual transaction is a reason to look closer. It is not, by itself, proof of malicious activity.</div>
        </aside>
      </section>

      <section id="how-it-works" className="border-y border-[#dce4de] bg-white">
        <div className="mx-auto grid max-w-6xl gap-10 px-5 py-16 sm:px-8 md:grid-cols-3 md:gap-8">
          {[
            ['Grounded in evidence', 'Important observations link back to available transaction facts and their source.'],
            ['Clear about uncertainty', 'Thin history, missing fields, and provider limitations are shown plainly.'],
            ['Remembers what you confirm', 'Label counterparties and respond to alerts. TRACE stores that context in Walrus Memory and shows exactly how it changes later analyses.'],
          ].map(([title, body], i) => <article key={title} className="border-t-2 border-[#176b50] pt-5"><p className="text-xs font-semibold tracking-[.12em] text-[#5f6c66]">0{i + 1}</p><h2 className="mt-4 text-xl font-semibold tracking-[-.025em]">{title}</h2><p className="mt-3 text-sm leading-6 text-[#5f6c66]">{body}</p></article>)}
        </div>
      </section>
      <section id="principles" className="mx-auto flex max-w-6xl flex-col gap-6 px-5 py-16 sm:px-8 md:flex-row md:items-center md:justify-between">
        <div><p className="text-xs font-semibold tracking-[.14em] text-[#176b50]">BUILT FOR TRUST</p><h2 className="mt-3 text-3xl font-semibold tracking-[-.04em]">A careful read of public data.</h2><p className="mt-3 max-w-2xl leading-7 text-[#5f6c66]">TRACE is a read-only intelligence tool. It does not custody assets, sign transactions, or guarantee that a wallet is safe.</p></div>
        <Link href="/analyze" className="inline-flex shrink-0 items-center justify-center gap-3 rounded-lg bg-[#176b50] px-5 py-3.5 font-medium text-white hover:bg-[#10533d]">Analyze a wallet <Arrow /></Link>
      </section>
      <footer className="border-t border-[#dce4de]"><div className="mx-auto flex max-w-6xl flex-col gap-2 px-5 py-6 text-sm text-[#5f6c66] sm:px-8 md:flex-row md:items-center md:justify-between"><span className="font-semibold tracking-[-.03em] text-[#17231f]">TRACE</span><span>Sui wallet intelligence · Read-only analysis</span></div></footer>
    </main>
  )
}
