import { cn } from "@/lib/utils"

export function CodeBlock({
  code,
  className,
}: {
  code: string
  className?: string
}) {
  return (
    <pre
      className={cn(
        "overflow-x-auto rounded-lg border bg-muted/40 p-3 text-[12.5px] leading-relaxed font-mono",
        className,
      )}
    >
      <code>{code}</code>
    </pre>
  )
}
