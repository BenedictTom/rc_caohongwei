/**
 * 极简 Jinja2-like 模板渲染器（仅支持 `{{ path.with.dots }}` 与 `| tojson`）。
 * 用于前端渲染预览；后端使用真实 Jinja2，仍以后端为准。
 */
function getPath(obj: unknown, path: string): unknown {
  return path
    .split(".")
    .reduce<unknown>((acc, key) => {
      if (acc == null) return undefined
      if (typeof acc !== "object") return undefined
      return (acc as Record<string, unknown>)[key]
    }, obj)
}

export function renderTemplate(
  tpl: string,
  ctx: Record<string, unknown>,
): string {
  return tpl.replace(/{{\s*([^}]+?)\s*}}/g, (_, expr: string) => {
    const [rawPath, ...filters] = expr.split("|").map((s) => s.trim())
    let value: unknown = getPath(ctx, rawPath)
    for (const f of filters) {
      if (f === "tojson") value = JSON.stringify(value)
    }
    if (value === undefined || value === null) {
      throw new Error(`字段不存在: ${rawPath}`)
    }
    return String(value)
  })
}
