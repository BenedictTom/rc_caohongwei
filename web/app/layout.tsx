import type { Metadata } from "next"
import "./globals.css"
import { Providers } from "@/components/providers"
import { Sidebar } from "@/components/sidebar"
import { Topbar } from "@/components/topbar"
import { PageTransition } from "@/components/page-transition"

export const metadata: Metadata = {
  title: "Notify Relay · 通知中转网关",
  description:
    "rc_caohongwei · spec-driven 的内部 API 通知中转服务可视化控制台",
  applicationName: "Notify Relay",
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="zh" suppressHydrationWarning>
      <body className="font-sans antialiased">
        <Providers>
          <div className="flex min-h-screen w-full">
            <Sidebar />
            <div className="flex min-w-0 flex-1 flex-col">
              <Topbar />
              <main className="flex-1 px-6 py-8 lg:px-10">
                <PageTransition>{children}</PageTransition>
              </main>
            </div>
          </div>
        </Providers>
      </body>
    </html>
  )
}
