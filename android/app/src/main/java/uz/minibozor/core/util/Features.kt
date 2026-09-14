package uz.minibozor.core.util

/**
 * Parts of the app whose backend is not there.
 *
 * A flag rather than deleted code, and rather than a screen that 404s. The
 * three states are not the same thing:
 *
 *   * **deleted** — the screens, view models and DTOs go, and putting the
 *     feature back means writing it again. Wrong here: the plan
 *     (`docs/rebuild-plan.md` §3) says reviews come back with a moderation
 *     screen of their own, so the work would be thrown away and redone.
 *   * **left reachable** — the section renders, the button navigates, and the
 *     screen behind it shows "topilmadi" because the endpoint answers 404.
 *     Worse than either: it tells the customer the app is broken.
 *   * **flagged off** — the entry points are absent, the code stays, and
 *     turning it back on is this file.
 *
 * So the rule for anything in here: gate the *entry point*, never the screen.
 * A screen nobody can reach costs nothing; a button that leads nowhere costs
 * the customer's trust in everything next to it.
 */
object Features {

    /**
     * Reviews: reading them, writing one, liking one, and "Sharhlarim".
     *
     * Off since the panels rebuild (2026-09-08) removed the whole review
     * system from the API — `routers/reviews.py`, `GET /products/{id}/reviews`,
     * `.../reviews/summary`, and the `reviews` / `review_likes` / `review_tags`
     * tables. Nine of the app's calls answer 404 while this is false, and all
     * nine are behind these entry points.
     *
     * `Product.rating` and `reviewsCount` still arrive on a product — they are
     * cached columns the seed wrote — so the *rating* keeps showing. That is
     * deliberate: a star rating with no reviews behind it is odd, but a
     * product page that suddenly has no rating at all reads as a regression.
     *
     * What to do when the API has reviews again: set this to true. Nothing
     * else.
     */
    const val REVIEWS = false

    /**
     * Promo codes in the basket.
     *
     * Off since the same rebuild dropped `POST /cart/promo` and the
     * `promo_codes` table. The cart's *shape* is untouched — it still accepts
     * a `promo_code` and still answers with `discount` and `promo_code`, so
     * nothing else on the basket screen had to change; `promo_discount` on
     * the server simply recognises no code. Only the field that asks for one
     * is hidden.
     */
    const val PROMO_CODES = false
}
