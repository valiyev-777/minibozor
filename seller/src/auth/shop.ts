import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"
import type { Shop } from "@/api/types"

export const SHOP = ["shop"]

/**
 * Which shop this is, as distinct from who signed in.
 *
 * `/staff/me` answers with the *user* — a phone number and a role — and says
 * nothing about the `sellers` row behind it. So this cabinet used to greet
 * people by phone number, and somebody just taken on had no way to confirm
 * they were linked to the right shop, which is the first thing they would
 * want to check.
 *
 * Kept out of the session context on purpose: the session is about being
 * signed in, and this is about the shop. Held for a long time because the
 * name and the commission rate change about once a year.
 */
export function useShop() {
  return useQuery({
    queryKey: SHOP,
    queryFn: () => api<Shop>("/staff/sellers/me"),
    staleTime: 5 * 60_000,
  })
}
