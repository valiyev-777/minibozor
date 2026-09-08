import { useSearchParams } from "react-router-dom"

/**
 * A list's filter, kept in the URL.
 *
 * Somebody who has narrowed a queue and then opened a row expects the
 * narrowing to still be there when they come back, and the browser's own back
 * button is what they will press. Component state loses that. A search
 * parameter survives the navigation, survives a reload, and can be sent to a
 * colleague — "look at /orders?status=placed" is a sentence people say.
 *
 * `replace` rather than push: changing a filter is not a place you want to
 * walk back through one tab at a time.
 *
 * The empty string means "everything", and is written to the URL as an empty
 * value rather than by deleting the parameter, so that "all" is a state
 * somebody chose rather than the absence of one — which is what makes a
 * default of `declared` possible at the same time.
 */
export function useFilter<T extends string>(
  key: string,
  fallback: T | "",
): [T | "", (next: T | "") => void] {
  const [params, setParams] = useSearchParams()
  const raw = params.get(key)
  const current = (raw === null ? fallback : raw) as T | ""

  const set = (next: T | "") => {
    const copy = new URLSearchParams(params)
    copy.set(key, next)
    setParams(copy, { replace: true })
  }
  return [current, set]
}
