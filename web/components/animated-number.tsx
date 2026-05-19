"use client"

import { animate, useMotionValue, useTransform, motion } from "framer-motion"
import { useEffect } from "react"

interface Props {
  value: number
  /** 小数位 */
  decimals?: number
  /** ms */
  duration?: number
  /** 后缀，例如 "%" */
  suffix?: string
  /** 前缀，例如 "$" */
  prefix?: string
  className?: string
}

export function AnimatedNumber({
  value,
  decimals = 0,
  duration = 800,
  suffix,
  prefix,
  className,
}: Props) {
  const mv = useMotionValue(0)
  const text = useTransform(mv, (n) =>
    `${prefix ?? ""}${n.toLocaleString(undefined, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    })}${suffix ?? ""}`,
  )
  useEffect(() => {
    const controls = animate(mv, value, {
      duration: duration / 1000,
      ease: [0.22, 0.61, 0.36, 1],
    })
    return controls.stop
  }, [mv, value, duration])

  return <motion.span className={className}>{text}</motion.span>
}
