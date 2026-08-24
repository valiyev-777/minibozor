# Mini Bozor — iOS

Native iOS client for the Mini Bozor marketplace, built from the 47-screen
"Shunaqa Tez" design. Swift + SwiftUI, `@Observable`, async/await, no third-party
dependencies.

## Build

```bash
open MiniBozor.xcodeproj
```

Requirements: Xcode 16, iOS 17 deployment target.

The checked-in project uses Xcode 16's synchronized file groups, so files added
to `MiniBozor/` are picked up without touching the project file. If you are on an
older Xcode, regenerate the project instead:

```bash
brew install xcodegen && xcodegen generate
```

Set your signing team on the target before running on a device.

## Point it at the backend

`Data/Networking/AppConfig.swift`:

| Build | API | Media |
|---|---|---|
| Debug | `http://localhost:8000/api/v1` | `http://localhost:8000/media` |
| Release | `https://api.minibozor.uz/api/v1` | `https://api.minibozor.uz/media` |

The simulator shares the Mac's `localhost`, so the local FastAPI server just
works. On a physical device, put your Mac's LAN address there instead.
`Info.plist` allows cleartext only through `NSAllowsLocalNetworking`, which
covers local hostnames and nothing else.

Start the backend with `cd ../backend && ./run.sh`, then sign in with
`+998 90 123 45 67`. Debug builds of the backend return the SMS code, and the
code screen shows it, so no gateway is needed.

## Structure

```
Core/DesignSystem/  MB.color / MB.type / MB.metric — mirrors design/tokens.json
Core/Icons/         the 30 glyphs plus the SVG path parser that draws them
Core/Components/    the shared kit: buttons, fields, rows, chips, product
                    tiles, tab bar, empty and error states
Core/Util/          money and Uzbek date formatting, Outcome/LoadState
Data/DTO/           Codable mirrors of the API payloads
Data/Networking/    APIClient actor, Keychain token store, config
Data/Repositories/  one repository per domain, all returning Outcome
Features/<area>/    view + @Observable model per design group
Features/Root/      session, router, tab scaffold, route table
```

### Icons

SwiftUI has no SVG path parser, so `Core/Icons/SVGPath.swift` implements the
subset the design uses (M/L/H/V/C/S/A and their relative forms, plus arcs).
That way both apps render the same geometry from `design/icons.json` — edit the
JSON and regenerate `MBIcons.swift` rather than hand-editing path data.

### Typography

The design is set in Plus Jakarta Sans. No font binaries are bundled: add the
TTFs to the target, list them under `UIAppFonts`, and set
`MBTypography.familyName`. Every style already requests the correct weight and
size, so nothing else changes.

## Screen map

| Design | View |
|---|---|
| 01–04 Onboarding | `OnboardingView` |
| 05–06 Kirish, SMS kod | `LoginView`, `OtpView` |
| 07 Bosh sahifa | `HomeView` |
| 08–09 Qidiruv | `SearchView`, `ListingView` |
| 10–12 Katalog, subkategoriya, turkum | `CatalogView`, `SubcategoryView`, `ListingView` |
| 13 Filtrlar | `FiltersSheet` |
| 14–16 Mahsulot, sharhlar, sharh yozish | `ProductView`, `ReviewsView`, `WriteReviewView` |
| 17–18 Savat | `CartView` |
| 19–24 Buyurtma berish → qabul qilindi | `Features/Checkout/` |
| 25–29 Yetkazish holati → qaytarish | `Features/Orders/` |
| 30–35 Profil → sevimlilar | `Features/Profile/` |
| 36–44 Bildirishnomalar → PIN | `Features/Settings/` |
| 45–47 Yordam, shartlar, chiqish | `HelpView`, `LegalView`, sign-out alert |

## Notes

- Tokens live in the Keychain (`kSecAttrAccessibleAfterFirstUnlock`), never in
  `UserDefaults`.
- `APIClient` refreshes once on a 401 and replays the request; concurrent
  callers await the same refresh rather than stampeding the endpoint. Refresh
  tokens are single-use server-side, so a replay signs the user out.
- The app never collects a card number. `AddCardView` hands off to the payment
  provider's own flow and the API only stores a processor token plus the last
  four digits.
- Each tab keeps its own navigation stack, so switching tabs preserves where the
  user was. The floating bar hides as soon as a tab pushes a screen, matching
  the design.
