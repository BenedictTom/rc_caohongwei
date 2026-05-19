import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

export function PageHeader({
  title,
  description,
  action,
  eyebrow,
}: {
  title: string
  description?: string
  action?: ReactNode
  eyebrow?: string
}) {
  return (
    <div className="relative mb-8">
      <div className="absolute inset-x-0 -top-12 -z-10 h-48 hero-grid opacity-50" />
      <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
        <div>
          {eyebrow && (
            <div className="mb-1 text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
              {eyebrow}
            </div>
          )}
          <h1 className="text-2xl font-semibold tracking-tight md:text-[28px]">
            {title}
          </h1>
          {description && (
            <p className="mt-1.5 max-w-2xl text-sm text-muted-foreground">
              {description}
            </p>
          )}
        </div>
        {action && <div className="flex items-center gap-2">{action}</div>}
      </div>
    </div>
  )
}

export function SectionTitle({
  title,
  hint,
  action,
  className,
}: {
  title: string
  hint?: string
  action?: ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        "mb-3 flex items-end justify-between gap-3",
        className,
      )}
    >
      <div>
        <h2 className="text-sm font-semibold tracking-tight">{title}</h2>
        {hint && (
          <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p>
        )}
      </div>
      {action}
    </div>
  )
}
