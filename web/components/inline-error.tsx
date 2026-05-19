import { AlertTriangle, RefreshCcw } from "lucide-react"
import { Button } from "@/components/ui/button"

export function InlineError({
  message = "数据加载失败",
  detail,
  onRetry,
}: {
  message?: string
  detail?: string
  onRetry?: () => void
}) {
  return (
    <div className="flex flex-col items-start gap-2 rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm">
      <div className="flex items-center gap-2 text-destructive">
        <AlertTriangle className="size-4" />
        <span className="font-medium">{message}</span>
      </div>
      {detail && (
        <p className="text-xs text-muted-foreground font-mono break-all">
          {detail}
        </p>
      )}
      {onRetry && (
        <Button
          size="sm"
          variant="outline"
          onClick={onRetry}
          className="mt-1"
        >
          <RefreshCcw className="mr-1 size-3.5" />
          重试
        </Button>
      )}
    </div>
  )
}
