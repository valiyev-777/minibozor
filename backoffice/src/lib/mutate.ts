import { useMutation, useQueryClient, type QueryKey } from "@tanstack/react-query"
import { toast } from "sonner"
import { ApiError } from "@/api/client"

/**
 * The one way a change is sent, and the one way a failure is shown.
 *
 * The backend answers 403, 409 and 422 with a sentence that is already
 * translated and already specific — "delivered holatidan packing holatiga
 * o'tib bo'lmaydi" is the whole explanation. Swallowing that behind a generic
 * message would leave the operator with nothing to act on, so the error text
 * goes straight into the toast.
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
