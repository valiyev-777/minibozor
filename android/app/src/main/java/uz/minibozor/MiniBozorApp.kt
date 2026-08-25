package uz.minibozor

import android.app.Application
import uz.minibozor.core.util.AppStrings
import coil.ImageLoader
import coil.ImageLoaderFactory
import dagger.hilt.android.HiltAndroidApp

@HiltAndroidApp
class MiniBozorApp : Application(), ImageLoaderFactory {

    override fun onCreate() {
        super.onCreate()
        AppStrings.init(this)
    }

    /**
     * The loader every AsyncImage in the app resolves to. Crossfade matters for
     * scroll feel: photos fading in over the warm placeholder read as smooth,
     * where the default instant swap reads as a flicker mid-fling.
     */
    override fun newImageLoader(): ImageLoader =
        ImageLoader.Builder(this)
            .crossfade(150)
            .build()
}
