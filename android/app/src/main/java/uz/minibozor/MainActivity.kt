package uz.minibozor

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import dagger.hilt.android.AndroidEntryPoint
import uz.minibozor.core.design.MiniBozorTheme
import uz.minibozor.navigation.MiniBozorNavHost

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        setContent {
            MiniBozorTheme {
                MiniBozorNavHost()
            }
        }
    }
}
