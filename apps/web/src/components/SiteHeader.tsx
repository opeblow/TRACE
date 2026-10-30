import Link from 'next/link'

const NAV = [
  { href: '/analyze', label: 'Analyze' },
  { href: '/alerts', label: 'Insights' },
  { href: '/memories', label: 'Memory' },
]

export default function SiteHeader({ current }: { current?: '/analyze' | '/alerts' | '/memories' }) {
  return (
    <header className="border-b border-[#dce4de] bg-[#fafaf7]">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-8 sm:py-4">
        <Link href="/" className="flex min-h-11 items-center gap-3" aria-label="TRACE home">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-[#176b50] text-sm font-bold text-white">T</span>
          <span className="text-lg font-semibold tracking-[-.04em]">TRACE</span>
        </Link>
        <nav aria-label="Main navigation" className="flex gap-1 text-sm text-[#5f6c66] sm:gap-6">
          {NAV.map(item => (
            <Link key={item.href} href={item.href} aria-current={current === item.href ? 'page' : undefined}
              className={`inline-flex min-h-11 items-center rounded-md px-2 ${current === item.href ? 'font-medium text-[#17231f]' : 'hover:text-[#17231f]'}`}>
              {item.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  )
}
