package uz.minibozor.navigation

import androidx.navigation.NavBackStackEntry

/**
 * The screen the customer was on when they changed the app's language.
 *
 * Changing the language throws the whole tree away and builds it again — that
 * is deliberate, because half the text on a product page is translated by the
 * server against the language the request asked for, so every screen needs a
 * new view model and a new fetch. What it also threw away was the navigation:
 * whoever switched to Russian on the settings screen was returned to the home
 * page, several taps from the switch they had just used, with no way to tell
 * whether it had worked.
 *
 * This outlives the tree, because it is neither in it nor in a view model.
 * [arm] is called at the moment the language changes; the new tree calls
 * [consume] once as it composes, and gets the route back exactly once. Kept
 * armed rather than always restoring, so a rebuild for any other reason — a
 * theme change, a rotation — is left to the navigator's own saved state.
 */
object LocaleRestart {

    @Volatile
    private var route: String? = null

    @Volatile
    private var armed = false

    /** Remembers where we are, on every destination change. */
    fun remember(entry: NavBackStackEntry?) {
        route = entry?.concreteRoute()
    }

    /** Called as the language changes, before the tree is rebuilt. */
    fun arm() {
        armed = true
    }

    /** The route to return to, once, or null. */
    fun consume(): String? {
        if (!armed) return null
        armed = false
        return route
    }
}

/**
 * A route that can be navigated to, rather than the pattern it was declared as.
 *
 * `destination.route` is the template — `product/{id}` — so it is the arguments
 * that turn it back into an address. Anything left unfilled means the entry did
 * not carry an argument its own pattern asks for, and a route with a `{` in it
 * would throw; those are dropped instead.
 */
/**
 * `{name}` in a route pattern.
 *
 * Both braces are escaped and the pattern is compiled once. Android's regex
 * engine is ICU rather than the JDK's, and it rejects a closing brace that
 * stands on its own — `\{([^}]+)}` compiles on the desktop and throws on the
 * phone, which crashed the app on every screen whose route takes an argument.
 */
private val Placeholder = Regex("""\{([^}]+)\}""")

private fun NavBackStackEntry.concreteRoute(): String? {
    val pattern = destination.route ?: return null
    if (!pattern.contains('{')) return pattern
    val args = arguments ?: return null
    val filled = Placeholder.replace(pattern) { match ->
        @Suppress("DEPRECATION")
        args.get(match.groupValues[1])?.toString() ?: match.value
    }
    return filled.takeUnless { it.contains('{') }
}
