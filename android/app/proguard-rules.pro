# Retrofit + kotlinx.serialization
-keepattributes Signature, InnerClasses, EnclosingMethod
-keepattributes RuntimeVisibleAnnotations, RuntimeVisibleParameterAnnotations
-keep,allowobfuscation,allowshrinking interface retrofit2.Call
-keep,allowobfuscation,allowshrinking class retrofit2.Response
-keep,allowobfuscation,allowshrinking class kotlin.coroutines.Continuation

-keepclassmembers class kotlinx.serialization.json.** { *; }
-keep,includedescriptorclasses class uz.minibozor.**$$serializer { *; }
-keepclassmembers class uz.minibozor.** { *** Companion; }
-keepclasseswithmembers class uz.minibozor.** { kotlinx.serialization.KSerializer serializer(...); }
