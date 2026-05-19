"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { useProviders, useSubmitNotification } from "@/lib/hooks"
import { PageHeader } from "@/components/section"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { CodeBlock } from "@/components/code-block"
import { renderTemplate } from "@/lib/template"
import { motion, AnimatePresence } from "framer-motion"
import {
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  Hash,
  Loader2,
  Send,
  Settings2,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { toast } from "sonner"
import type { Provider } from "@/lib/types"

const STEPS = ["选择 Provider", "编辑 Payload", "确认与提交"] as const

const SAMPLE: Record<string, string> = {
  "demo-crm": `{
  "user_id": 4321,
  "event": "subscription.paid",
  "metadata": {"plan": "pro"}
}`,
  "demo-ad-network": `{
  "click_id": "clk_abc123",
  "ts": "${new Date().toISOString()}"
}`,
  "demo-inventory": `{
  "sku": "SKU-1024",
  "qty": 2
}`,
}

export default function NewNotificationPage() {
  const router = useRouter()
  const { data: providers, isLoading: loadingProviders } = useProviders()
  const submit = useSubmitNotification()

  const [step, setStep] = useState(0)
  const [provider, setProvider] = useState<Provider | null>(null)
  const [payloadText, setPayloadText] = useState("")
  const [idempotencyKey, setIdempotencyKey] = useState("")

  const parseError = parsePayload(payloadText)
  const renderError = (() => {
    if (parseError || !provider) return null
    try {
      renderTemplate(provider.bodyTemplate, { payload: JSON.parse(payloadText) })
      return null
    } catch (e) {
      return e instanceof Error ? e.message : String(e)
    }
  })()

  const canNext =
    step === 0
      ? !!provider
      : step === 1
        ? !parseError
        : true

  const handleSubmit = async () => {
    if (!provider) return
    try {
      const result = await submit.mutateAsync({
        provider: provider.name,
        payload: JSON.parse(payloadText),
        idempotencyKey: idempotencyKey || undefined,
      })
      toast.success(`已受理 · ${result.id}`, {
        description: result.duplicated ? "幂等命中：返回已存在的通知" : undefined,
      })
      setTimeout(() => router.push(`/notifications`), 1100)
    } catch (e) {
      toast.error("提交失败", {
        description: e instanceof Error ? e.message : String(e),
      })
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="新建"
        title="发起一次通知"
        description="选择 Provider → 编辑 payload（自动渲染目标 HTTP 请求预览）→ 确认提交。"
        action={
          <Button variant="ghost" onClick={() => router.back()}>
            <ArrowLeft className="mr-1 size-4" />
            返回
          </Button>
        }
      />

      {/* 步骤指示器 */}
      <div className="relative flex items-center gap-3">
        {STEPS.map((label, i) => (
          <div key={label} className="flex items-center gap-3">
            <div className="flex items-center gap-2.5">
              <span
                className={cn(
                  "relative flex size-7 items-center justify-center rounded-full border text-xs font-semibold transition-all",
                  i < step
                    ? "border-success bg-success text-success-foreground"
                    : i === step
                      ? "border-foreground bg-foreground text-background"
                      : "border-border bg-background text-muted-foreground",
                )}
              >
                {i < step ? <Check className="size-3.5" /> : i + 1}
              </span>
              <span
                className={cn(
                  "text-sm font-medium transition-colors",
                  i <= step ? "text-foreground" : "text-muted-foreground",
                )}
              >
                {label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div
                className={cn(
                  "h-px w-12 transition-colors",
                  i < step ? "bg-success" : "bg-border",
                )}
              />
            )}
          </div>
        ))}
      </div>

      <Card className="overflow-hidden">
        <CardContent className="p-6">
          <AnimatePresence mode="wait">
            <motion.div
              key={step}
              initial={{ opacity: 0, x: 12 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -12 }}
              transition={{ duration: 0.22 }}
            >
              {step === 0 && (
                <div className="grid gap-3 md:grid-cols-3">
                  {loadingProviders || !providers
                    ? Array.from({ length: 3 }).map((_, i) => (
                        <Skeleton key={i} className="h-32" />
                      ))
                    : providers.map((p) => {
                        const active = provider?.name === p.name
                        return (
                          <button
                            key={p.name}
                            type="button"
                            onClick={() => {
                              setProvider(p)
                              // 不同 provider 的字段 schema 不同，切换时直接覆盖样例，
                              // 避免把 A 的 payload 喂进 B 的 bodyTemplate 触发"字段不存在"。
                              setPayloadText(SAMPLE[p.name] ?? "{}")
                            }}
                            className={cn(
                              "group rounded-xl border bg-card p-4 text-left transition-all",
                              active
                                ? "border-foreground shadow-md ring-2 ring-foreground/15"
                                : "hover:-translate-y-0.5 hover:shadow-md",
                            )}
                          >
                            <div className="flex items-center justify-between">
                              <div className="text-sm font-semibold">{p.name}</div>
                              <Settings2 className="size-3.5 text-muted-foreground" />
                            </div>
                            <div className="mt-1 truncate font-mono text-[11px] text-muted-foreground">
                              {p.method} {p.url.replace(/^https?:\/\//, "")}
                            </div>
                            <div className="mt-3 flex items-center gap-2 text-[11px] text-muted-foreground">
                              <span className="rounded-md bg-muted px-1.5 py-0.5 font-mono">
                                {p.authType}
                              </span>
                              <span>· {p.timeoutMs}ms 超时</span>
                            </div>
                          </button>
                        )
                      })}
                </div>
              )}

              {step === 1 && provider && (
                <div className="grid gap-5 lg:grid-cols-2">
                  <div className="space-y-2">
                    <Label className="flex items-center justify-between">
                      <span>Payload (JSON)</span>
                      <span className="text-[11px] text-muted-foreground">
                        ≤ 64 KB
                      </span>
                    </Label>
                    <textarea
                      value={payloadText}
                      onChange={(e) => setPayloadText(e.target.value)}
                      rows={14}
                      spellCheck={false}
                      className={cn(
                        "w-full resize-y rounded-lg border bg-background p-3 font-mono text-[12.5px] leading-relaxed shadow-xs transition-shadow focus:outline-none focus-visible:ring-2 focus-visible:ring-ring/40",
                        parseError && "border-destructive/50",
                      )}
                    />
                    <p
                      className={cn(
                        "text-xs",
                        parseError ? "text-destructive" : "text-muted-foreground",
                      )}
                    >
                      {parseError ?? "JSON 合法"}
                    </p>
                    <div className="pt-2 space-y-1.5">
                      <Label className="flex items-center gap-1.5">
                        <Hash className="size-3.5" />
                        Idempotency-Key (可选)
                      </Label>
                      <Input
                        value={idempotencyKey}
                        onChange={(e) => setIdempotencyKey(e.target.value)}
                        placeholder="留空则自动按 sha256(provider+payload) 兜底"
                        className="font-mono text-xs"
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label>渲染预览</Label>
                    <div className="rounded-lg border bg-muted/30 p-3 text-[11px] uppercase tracking-wider text-muted-foreground">
                      {provider.method} {provider.url}
                    </div>
                    <CodeBlock
                      code={Object.entries(provider.headers)
                        .map(([k, v]) => `${k}: ${v}`)
                        .join("\n")}
                    />
                    {parseError ? (
                      <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 font-mono text-xs text-destructive">
                        无法渲染：先修复 JSON
                      </div>
                    ) : renderError ? (
                      <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 font-mono text-xs text-destructive">
                        渲染失败：{renderError}
                      </div>
                    ) : (
                      <CodeBlock
                        code={renderTemplate(provider.bodyTemplate, {
                          payload: JSON.parse(payloadText),
                        })}
                      />
                    )}
                  </div>
                </div>
              )}

              {step === 2 && provider && (
                <div className="space-y-4">
                  <div className="rounded-xl border bg-muted/30 p-5">
                    <div className="text-xs uppercase tracking-wider text-muted-foreground">
                      即将发送
                    </div>
                    <div className="mt-1 text-lg font-semibold">
                      {provider.name}
                    </div>
                    <div className="mt-0.5 truncate font-mono text-xs text-muted-foreground">
                      {provider.method} {provider.url}
                    </div>
                  </div>
                  <div className="grid gap-4 lg:grid-cols-2">
                    <div className="space-y-1.5">
                      <Label>Payload</Label>
                      <CodeBlock code={payloadText} />
                    </div>
                    <div className="space-y-1.5">
                      <Label>Idempotency-Key</Label>
                      <CodeBlock
                        code={idempotencyKey || "(自动生成)"}
                        className="text-[12px]"
                      />
                    </div>
                  </div>
                </div>
              )}
            </motion.div>
          </AnimatePresence>
        </CardContent>

        <div className="flex items-center justify-between border-t bg-muted/20 px-6 py-3">
          <Button
            variant="ghost"
            disabled={step === 0 || submit.isPending}
            onClick={() => setStep((s) => Math.max(0, s - 1))}
          >
            <ArrowLeft className="mr-1 size-4" />
            上一步
          </Button>
          {step < STEPS.length - 1 ? (
            <Button
              disabled={!canNext}
              onClick={() => setStep((s) => Math.min(STEPS.length - 1, s + 1))}
            >
              下一步
              <ArrowRight className="ml-1 size-4" />
            </Button>
          ) : (
            <Button
              onClick={handleSubmit}
              disabled={submit.isPending || submit.isSuccess}
              className={cn(
                "min-w-[7rem] transition-colors",
                submit.isSuccess && "bg-success hover:bg-success",
              )}
            >
              {submit.isSuccess ? (
                <CheckCircle2 className="size-4" />
              ) : submit.isPending ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <>
                  <Send className="mr-1.5 size-4" />
                  提交
                </>
              )}
            </Button>
          )}
        </div>
      </Card>
    </div>
  )
}

function parsePayload(text: string): string | null {
  if (!text.trim()) return "请填写 JSON"
  try {
    const v = JSON.parse(text)
    if (typeof v !== "object" || v === null || Array.isArray(v))
      return "顶层必须是 JSON 对象"
    return null
  } catch (e) {
    return e instanceof Error ? `JSON 解析失败：${e.message}` : "JSON 解析失败"
  }
}
