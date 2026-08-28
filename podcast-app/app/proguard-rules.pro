# Keep JNI entry points and Room constructors.
-keepclasseswithmembernames class * { native <methods>; }
-keep class * extends androidx.room.RoomDatabase { *; }
