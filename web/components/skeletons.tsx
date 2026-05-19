import { Skeleton } from "@/components/ui/skeleton"
import { Card, CardContent, CardHeader } from "@/components/ui/card"

export function MetricCardSkeleton() {
  return (
    <Card>
      <CardHeader className="pb-2">
        <Skeleton className="h-3.5 w-20" />
      </CardHeader>
      <CardContent className="space-y-2">
        <Skeleton className="h-8 w-24" />
        <Skeleton className="h-3 w-32" />
      </CardContent>
    </Card>
  )
}

export function RowSkeleton() {
  return (
    <div className="flex items-center gap-3 px-4 py-3">
      <Skeleton className="h-3.5 w-32" />
      <Skeleton className="h-3.5 w-20" />
      <Skeleton className="h-3.5 w-16" />
      <Skeleton className="ml-auto h-3.5 w-24" />
    </div>
  )
}
