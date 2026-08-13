plugins { id("com.android.application") }

android {
    namespace = "dev.moket.ttsbench"
    compileSdk = 35
    defaultConfig {
        applicationId = "dev.moket.ttsbench"
        minSdk = 28
        targetSdk = 35
        versionCode = 1
        versionName = "0.1"
        ndk { abiFilters += "arm64-v8a" }
        testInstrumentationRunner = "android.test.InstrumentationTestRunner"
    }
    buildTypes { release { isMinifyEnabled = false } }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    testOptions { unitTests.isReturnDefaultValues = true }
    sourceSets["main"].jniLibs.srcDir("../libs")
}

dependencies {
    // Runtime is staged as libs/sherpa-onnx-1.13.5.aar by fetch-sherpa-aar.py.
    if (file("../libs/sherpa-onnx-1.13.5.aar").exists()) implementation(files("../libs/sherpa-onnx-1.13.5.aar"))
    testImplementation("junit:junit:4.13.2")
}
