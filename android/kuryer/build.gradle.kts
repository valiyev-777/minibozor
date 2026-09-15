plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
}

/**
 * The courier's app: a window onto the web app, not a second implementation.
 *
 * The courier screens already exist in `web/` — `/ishlarim`, `/tarix`,
 * `/daromad` — and they are a phone app already: the role gets its own
 * navigation and the comfortable density. Writing them again in Compose would
 * be two codebases answering one question, and the second one always lags.
 *
 * So this module is deliberately tiny. What it buys over "open it in Chrome":
 * an icon on the home screen, no address bar, and — the real reason — a
 * WebView is not held to a secure context, so it works over plain `http` on
 * the shop's wifi. An installed PWA cannot: Chrome refuses to install one from
 * `http://192.168.x.x`, which is every address this shop actually has.
 */
android {
    namespace = "uz.minibozor.kuryer"
    compileSdk = 35

    defaultConfig {
        applicationId = "uz.minibozor.kuryer"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "1.0"

        // Where the web app is served. The default is this machine on the
        // shop's wifi; override without editing the file:
        //     gradle :kuryer:assembleDebug -Pkuryer.url=http://10.0.0.5:5174
        // The phone can also be given `adb reverse tcp:5174 tcp:5174` and this
        // pointed at http://localhost:5174, which is how it is tested on a
        // cable.
        val home = (project.findProperty("kuryer.url") as String?)
            ?: "http://192.168.100.58:5174"
        buildConfigField("String", "HOME_URL", "\"$home\"")
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    buildFeatures {
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }

    kotlinOptions {
        jvmTarget = "11"
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.appcompat)
}
