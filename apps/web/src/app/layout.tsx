import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'TRACE — Understand your Sui wallet',
  description: 'Read-only wallet intelligence with clear evidence, uncertainty, and user-controlled context.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body>{children}</body></html>
}
