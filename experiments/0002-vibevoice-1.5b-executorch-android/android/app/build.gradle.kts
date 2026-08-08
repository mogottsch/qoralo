plugins {
    id("com.android.application")
}

android {
    namespace = "dev.moket.vibevoiceprobe"
    compileSdk = 35

    defaultConfig {
        applicationId = "dev.moket.vibevoiceprobe"
        minSdk = 28
        targetSdk = 35
        versionCode = 1
        versionName = "0.1"
    }

    buildTypes {
        debug {
            isDebuggable = true
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    packaging {
        jniLibs.useLegacyPackaging = true
    }
}

dependencies {
    implementation("org.pytorch:executorch-android:1.2.0")
}
