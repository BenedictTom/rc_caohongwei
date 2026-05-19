"use client"

import { BookOpen } from "lucide-react"
import Link from "next/link"
import { Badge } from "@/components/ui/badge"
import { buttonVariants } from "@/components/ui/button"
import { ThemeToggle } from "@/components/theme-toggle"
import { apiMode } from "@/lib/api"
import { cn } from "@/lib/utils"

export function Topbar() {
  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b bg-background/70 px-6 backdrop-blur-xl">
      <div className="flex items-center gap-2">
        <Badge
          variant="secondary"
          className="font-mono text-[11px] uppercase tracking-wider"
        >
          {apiMode === "mock" ? "MOCK 模式" : "REAL 模式"}
        </Badge>
        <span className="text-xs text-muted-foreground hidden md:inline">
          {apiMode === "mock"
            ? "未配置 NEXT_PUBLIC_API_BASE，使用本地 mock 数据"
            : "已连接真实后端"}
        </span>
      </div>
      <div className="ml-auto flex items-center gap-1.5">
        <Link
          href="/"
          aria-label="文档"
          className={cn(buttonVariants({ variant: "ghost", size: "icon" }))}
        >
          <BookOpen className="size-4" />
        </Link>
        <ThemeToggle />
        <div className="ml-1 size-8 rounded-full bg-gradient-to-br from-foreground/80 to-muted-foreground/40" />
      </div>
    </header>
  )
}
