/**
 * One key per action, and the same key for every retry of it.
 *
 * Every write in `/courier/*` requires an `Idempotency-Key` header, and the
 * reason is the sentence the whole design exists for: "delivered, 240 000
 * so'm at the door". A retry without a key is a second sale off the shelf,
 * and nobody notices until the shelf is short.
 *
 * **The key belongs to the action, not to the request.** A courier presses
 * "Yetkazdim", the phone loses signal in a stairwell, they press it again —
 * that is one delivery pressed twice, and both attempts must carry the same
 * key so the second replays the first answer instead of doing it again. So the
 * key is derived from *what is being done to what*: this order, delivered.
 *
 * Not a fresh uuid per press, which is what a naive client does and which
 * turns every retry into a new request. Not stored, either: the offline outbox
 * is deliberately out of the first version (see the README), so a key only has
 * to survive the retries inside one screen's lifetime — and a reload is a new
 * decision by a person who can see the current state.
 */
export function actionKey(kind: string, id: number, attempt = 0): string {
  // The attempt number is in the key so a courier who was *refused* — a 409
  // on a cash figure that did not match, say — can correct it and send again
  // rather than being handed the refusal back for ever.
  return attempt === 0 ? `${kind}-${id}` : `${kind}-${id}-${attempt}`
}
