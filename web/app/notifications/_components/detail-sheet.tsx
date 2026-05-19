"use client"

import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { CodeBlock } from "@/components/code-block"
import { StatusBadge } from "@/components/status-badge"
import { Hash } from "lucide-react"
import type { Notification } from "@/lib/types"
import { format } from "date-fns"
import { useProviders } from "@/lib/hooks"
import { renderTemplate } from "@/lib/template"

export function DetailSheet({
  notification,
  open,
  onOpenChange,
}: {
  notification: Notification | null
  open: boolean
  onOpenChange: (v: boolean) => void
}) {
  const { data: providers } = useProviders()
  const provider = providers?.find((p) => p.name === notification?.provider)

  const renderedBody = notification && provider
    ? safeRender(provider.bodyTemplate, notification.payload)
    : ""

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-xl gap-0 p-0">
        {notification && (
          <>
            <SheetHeader className="border-b px-6 pt-6 pb-4">
              <div className="mb-2 flex items-center gap-2">
                <StatusBadge status={notification.status} />
                <span className="text-xs text-muted-foreground">
                  · {notification.attempts} 次尝试
                </span>
              </div>
              <SheetTitle className="font-mono text-base">
                {notification.id}
              </SheetTitle>
              <SheetDescription className="flex items-center gap-1.5 font-mono text-[11px]">
                <Hash className="size-3" />
                {notification.idempotencyKey}
              </SheetDescription>
            </SheetHeader>

            <ScrollArea className="h-[calc(100vh-130px)]">
              <div className="px-6 py-5 space-y-5">
                <Meta notification={notification} />

                <Tabs defaultValue="payload">
                  <TabsList className="grid w-full grid-cols-2">
                    <TabsTrigger value="payload">Payload</TabsTrigger>
                    <TabsTrigger value="rendered">渲染预览</TabsTrigger>
                  </TabsList>
                  <TabsContent value="payload" className="mt-3">
                    <CodeBlock
                      code={JSON.stringify(notification.payload, null, 2)}
                    />
                  </TabsContent>
                  <TabsContent value="rendered" className="mt-3 space-y-2">
                    {provider ? (
                      <>
                        <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
                          {provider.method}
                        </div>
                        <div className="break-all rounded-md border bg-muted/30 px-3 py-2 font-mono text-[12.5px]">
                          {provider.url}
                        </div>
                        <div className="text-[11px] uppercase tracking-wider text-muted-foreground pt-2">
                          Headers
                        </div>
                        <CodeBlock
                          code={Object.entries(provider.headers)
                            .map(([k, v]) => `${k}: ${v}`)
                            .join("\n")}
                        />
                        <div className="text-[11px] uppercase tracking-wider text-muted-foreground pt-2">
                          Body
                        </div>
                        <CodeBlock code={renderedBody} />
                      </>
                    ) : (
                      <div className="text-sm text-muted-foreground">
                        Provider 配置未找到
                      </div>
                    )}
                  </TabsContent>
                </Tabs>
              </div>
            </ScrollArea>
          </>
        )}
      </SheetContent>
    </Sheet>
  )
}

function safeRender(tpl: string, payload: Record<string, unknown>) {
  try {
    return renderTemplate(tpl, { payload })
  } catch (e) {
    return `[渲染失败] ${e instanceof Error ? e.message : String(e)}`
  }
}

function Meta({ notification }: { notification: Notification }) {
  const items: { label: string; value: string }[] = [
    { label: "Provider", value: notification.provider },
    {
      label: "创建于",
      value: format(new Date(notification.createdAt), "yyyy-MM-dd HH:mm:ss"),
    },
  ]
  if (notification.deliveredAt) {
    items.push({
      label: "送达于",
      value: format(new Date(notification.deliveredAt), "yyyy-MM-dd HH:mm:ss"),
    })
  }
  if (notification.nextRetryAt) {
    items.push({
      label: "下次重试",
      value: format(new Date(notification.nextRetryAt), "yyyy-MM-dd HH:mm:ss"),
    })
  }
  if (notification.lastError) {
    items.push({ label: "最后错误", value: notification.lastError })
  }
  if (notification.lastResponseSummary) {
    items.push({ label: "最后响应", value: notification.lastResponseSummary })
  }
  return (
    <dl className="grid grid-cols-3 gap-2 text-sm">
      {items.map((it) => (
        <div key={it.label} className="col-span-3 flex items-baseline gap-3">
          <dt className="w-20 shrink-0 text-xs uppercase tracking-wider text-muted-foreground">
            {it.label}
          </dt>
          <dd className="min-w-0 flex-1 truncate font-medium">{it.value}</dd>
        </div>
      ))}
      <Separator className="col-span-3 my-1" />
    </dl>
  )
}

