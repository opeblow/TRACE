import type { Metadata, Viewport } from 'next'
import { Geist, Geist_Mono, Instrument_Serif } from 'next/font/google'
import './globals.css'

// next/font downloads these at build time and serves them from our own origin,
// so the CSP's font-src 'self' still holds.
const sans = Geist({ subsets: ['latin'], variable: '--font-sans', display: 'swap' })
const mono = Geist_Mono({ subsets: ['latin'], variable: '--font-mono', display: 'swap' })
const serif = Instrument_Serif({ subsets: ['latin'], weight: '400', style: ['normal', 'italic'], variable: '--font-serif', display: 'swap' })

export const metadata: Metadata = {
  title: 'TRACE — Understand your Sui wallet',
  description: 'Read-only wallet intelligence with clear evidence, uncertainty, and user-controlled context.',
  applicationName: 'TRACE',
  openGraph: { title: 'TRACE', description: 'Sui wallet intelligence that remembers what you confirm.', images: ['/icon-512.png'] },
}

export const viewport: Viewport = {
  themeColor: '#176B50',
  width: 'device-width',
  initialScale: 1,
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en" className={`${sans.variable} ${mono.variable} ${serif.variable}`}><body>{children}</body></html>
}
