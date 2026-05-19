"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { motion } from "framer-motion"
import {
  LayoutDashboard,
  Send,
  Inbox,
  AlertTriangle,
  Settings2,
  Sparkles,
} from "lucide-react"
import { cn } from "@/lib/utils"

const NAV = [
  { href: "/", label: "概览", icon: LayoutDashboard },
  { href: "/notifications", label: "通知列表", icon: Inbox },
  { href: "/notifications/new", label: "新建通知", icon: Send },
  { href: "/dead-letters", label: "死信队列", icon: AlertTriangle },
  { href: "/providers", label: "供应商", icon: Settings2 },
] as const

export function Sidebar() {
  const pathname = usePathname()

  return (
    <aside className="hidden lg:flex w-60 shrink-0 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground">
      <div className="flex h-16 items-center gap-2.5 px-5 border-b border-sidebar-border">
        <div className="flex size-9 items-center justify-center rounded-lg bg-gradient-to-br from-foreground to-muted-foreground/70 text-background shadow-sm">
          <Sparkles className="size-4" />
        </div>
        <div className="flex flex-col leading-tight">
          <span className="text-sm font-semibold tracking-tight">Notify Relay</span>
          <span className="text-[11px] text-muted-foreground">通知中转网关</span>
        </div>
      </div>
      <nav className="flex flex-1 flex-col gap-1 p-3">
        {NAV.map((item) => {
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href)
          const Icon = item.icon
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                active
                  ? "text-sidebar-foreground"
                  : "text-muted-foreground hover:text-sidebar-foreground hover:bg-sidebar-accent",
              )}
            >
              {active && (
                <motion.span
                  layoutId="sidebar-pill"
                  className="absolute inset-0 rounded-lg bg-sidebar-accent"
                  transition={{ type: "spring", stiffness: 380, damping: 32 }}
                />
              )}
              <Icon
                className={cn(
                  "relative size-4 transition-colors",
                  active ? "text-foreground" : "text-muted-foreground group-hover:text-foreground",
                )}
              />
              <span className="relative font-medium">{item.label}</span>
            </Link>
          )
        })}
      </nav>
      <div className="px-4 py-4 border-t border-sidebar-border text-[11px] text-muted-foreground leading-relaxed">
        <div>spec-driven · OpenSpec</div>
        <div className="mt-0.5 opacity-70">rc_caohongwei · v0.1</div>
      </div>
    </aside>
  )
}
