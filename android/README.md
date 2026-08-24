# Mini Bozor — Android

Native Android client for the Mini Bozor marketplace, built from the 47-screen
"Shunaqa Tez" design. Kotlin + Jetpack Compose, Hilt, Retrofit, Coil.

## Build

The repo ships the Gradle wrapper *properties* but not the wrapper jar, so do one
of the following once:

```bash
gradle wrapper        # if you have Gradle 8.x installed
```

or just open `android/` in Android Studio (Ladybug or newer) and let it sync —
it will create the wrapper for you.

Then:

```bash
./gradlew :app:installDebug
```

Requirements: JDK 17, Android SDK 35, minSdk 26.

## Point it at the backend

`app/build.gradle.kts` sets the base URLs per build type:

| Build | API | Media |
|---|---|---|
| debug | `http://10.0.2.2:8000/api/v1/` | `http://10.0.2.2:8000/media` |
| release | `https://api.minibozor.uz/api/v1/` | `https://api.minibozor.uz/media` |

`10.0.2.2` is the host machine as seen from the Android emulator. On a physical
device use your machine's LAN address and add it to
`res/xml/network_security_config.xml` (cleartext is allowed only for the local
hosts listed there).

Start the backend with `cd ../backend && ./run.sh`, then sign in with
`+998 90 123 45 67`. Debug builds print the SMS code on the code screen, so no
gateway is needed.

## Structure

```
core/design/       colours, type, dimens, shapes, theme
core/design/icon/  the design's 30 glyphs as stroked ImageVectors
core/design/component/  the shared kit: buttons, fields, rows, chips,
                        product tiles, tab bar, empty/error states
core/util/         money and Uzbek date formatting, Outcome wrapper
data/remote/       Retrofit API, DTOs, auth interceptor + token refresh
data/local/        encrypted token store, DataStore preferences
data/repository/   one repository per domain, all returning Outcome
ui/<feature>/      screen + view model per design group
navigation/        routes, nav host, tab scaffold
```

### Design tokens

Colours, type scale, spacing and component metrics come from
`../design/tokens.json` and live in `core/design/`. The icon set is generated
from `../design/icons.json` into `MbIcons.kt` — edit the JSON and regenerate
rather than hand-editing path data.

### Typography

The design is set in Plus Jakarta Sans. No font binaries are bundled: drop the
five TTFs into `res/font/` and point `JakartaSans` in `core/design/Type.kt` at a
real `FontFamily`. Every style already requests the correct weight, so nothing
else changes.

## Screen map

| Design | Destination |
|---|---|
| 01–04 Onboarding | `OnboardingScreen` |
| 05–06 Kirish, SMS kod | `LoginScreen`, `OtpScreen` |
| 07 Bosh sahifa | `HomeScreen` |
| 08–09 Qidiruv | `SearchScreen`, `ListingScreen` |
| 10–12 Katalog, subkategoriya, turkum | `CatalogScreen`, `SubcategoryScreen`, `ListingScreen` |
| 13 Filtrlar | `FiltersSheet` |
| 14–16 Mahsulot, sharhlar, sharh yozish | `ProductScreen`, `ReviewsScreen`, `WriteReviewScreen` |
| 17–18 Savat | `CartScreen` |
| 19–24 Buyurtma berish → qabul qilindi | `checkout/` |
| 25–29 Yetkazish holati → qaytarish | `orders/` |
| 30–35 Profil → sevimlilar | `profile/` |
| 36–44 Bildirishnomalar → PIN | `settings/` |
| 45–47 Yordam, shartlar, chiqish | `HelpScreen`, `LegalScreen`, `SignOutDialog` |

## Security notes

- Tokens live in `EncryptedSharedPreferences`; the refresh token is never in
  plaintext on disk.
- `TokenAuthenticator` refreshes once on a 401 and replays the request. Refresh
  tokens are single-use server-side, so a replay signs the user out.
- The app never collects a card number. `AddCardScreen` hands off to the payment
  provider's own flow and the API only stores a processor token plus the last
  four digits.
