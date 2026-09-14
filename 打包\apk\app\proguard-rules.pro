# Chaquopy rules
-keep class com.chaquo.python.** { *; }
-dontwarn com.chaquo.python.**

# Keep bridge classes
-keep class com.qihhao.pos.** { *; }

# Keep all project classes (Python modules won't be here but just in case)
-keepnames class com.qihhao.pos.**

# BuildConfig
-keep class **.BuildConfig { *; }

# Preserve Kotlin metadata
-keepattributes *Annotation*, InnerClasses
-keepclassmembers class kotlin.Metadata {
    public <methods>;
}

# Models for static analysis
-keepclassmembers class * {
    @com.google.gson.annotations.SerializedName <fields>;
}
