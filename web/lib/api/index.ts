import * as mock from "./mock"
import { createRealClient } from "./real"

const BASE = process.env.NEXT_PUBLIC_API_BASE

export const apiMode: "mock" | "real" = BASE ? "real" : "mock"

export const api = BASE ? createRealClient(BASE) : mock

if (typeof window !== "undefined") {
  console.info(`[api] ${apiMode} mode`)
}
