import type { Metadata, Viewport } from 'next'
import './globals.css'

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
  return <html lang="en"><body>{children}</body></html>
}
