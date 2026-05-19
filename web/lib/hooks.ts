"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import type {
  DeadLettersQuery,
  NotificationsQuery,
  SubmitNotificationInput,
} from "@/lib/types"

export function useMetrics() {
  return useQuery({
    queryKey: ["metrics"],
    queryFn: () => api.getMetrics(),
    refetchInterval: 10_000,
    staleTime: 5_000,
  })
}

export function useProviders() {
  return useQuery({
    queryKey: ["providers"],
    queryFn: () => api.listProviders(),
    refetchInterval: 30_000,
  })
}

export function useNotifications(q: NotificationsQuery) {
  return useQuery({
    queryKey: ["notifications", q],
    queryFn: () => api.listNotifications(q),
    placeholderData: (prev) => prev,
    staleTime: 4_000,
  })
}

export function useDeadLetters(q: DeadLettersQuery) {
  return useQuery({
    queryKey: ["dead-letters", q],
    queryFn: () => api.listDeadLetters(q),
    placeholderData: (prev) => prev,
  })
}

export function useSubmitNotification() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: SubmitNotificationInput) => api.submitNotification(input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notifications"] })
      qc.invalidateQueries({ queryKey: ["metrics"] })
    },
  })
}
