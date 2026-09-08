import { useMutation, useQueryClient, type QueryKey } from "@tanstack/react-query"
import { toast } from "sonner"
import { ApiError } from "@/api/client"

/**
 * The one way a change is sent, and the one way a failure is shown.
 *
 * The backend answers 400, 403 and 409 with a sentence that is already
 * translated and already specific — "Naqd 240 000 bo'lishi kerak, 230 000
 * berildi", "Bu sizning reysingiz emas". That text goes straight into the
 * toast. There is no "something went wrong" in this codebase; the person
 * reading it is standing at a door with a parcel, and a shrug is worse than
 * no message at all.
 */
export function useAction<TArgs, TResult>(options: {
  run: (args: TArgs) => Promise<TResult>
  invalidate?: QueryKey[]
  success?: string | ((result: TResult) => string)
  onDone?: (result: TResult) => void
}) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: options.run,
    onSuccess: (result) => {
      const message =
        typeof options.success === "function" ? options.success(result) : options.success
      if (message) toast.success(message)
      for (const key of options.invalidate ?? []) {
        void queryClient.invalidateQueries({ queryKey: key })
      }
      options.onDone?.(result)
    },
    onError: (error: unknown) => {
      toast.error(
        error instanceof ApiError ? error.message : "So'rov bajarilmadi.",
        error instanceof ApiError && error.status ? { description: `HTTP ${error.status}` } : {},
      )
    },
  })
}
