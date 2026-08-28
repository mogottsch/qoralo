import java.util.Properties
import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("com.google.devtools.ksp")
}

val localProperties = Properties().apply {
    val file = rootProject.file("local.properties")
    if (file.isFile) file.inputStream().use(::load)
}
fun pinnedHash(name: String): String = localProperties.getProperty(name, "").replace("\\", "\\\\").replace("\"", "\\\"")
val nativeRuntimeEnabled = localProperties.getProperty("native.runtime.enabled", "false").toBoolean()

android {
    namespace = "dev.vibevoice.podcast"
    compileSdk = 35

    defaultConfig {
        applicationId = "dev.vibevoice.podcast.internal"
        minSdk = 29
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0-internal"
        buildConfigField("String", "GEMMA_MANIFEST_SHA256", "\"${pinnedHash("gemma.manifest.sha256")}\"")
        buildConfigField("String", "SUPERTONIC_MANIFEST_SHA256", "\"${pinnedHash("supertonic.manifest.sha256")}\"")

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        vectorDrawables.useSupportLibrary = true
        ndk { abiFilters += "arm64-v8a" }
        if (nativeRuntimeEnabled) {
            externalNativeBuild.cmake {
                arguments += listOf(
                    "-DONNXRUNTIME_INCLUDE_DIR=${localProperties.getProperty("onnxruntime.include.dir")}",
                    "-DONNXRUNTIME_LIBRARY=${project.file("runtime-libs/arm64-v8a/libonnxruntime.so")}",
                )
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures { compose = true; buildConfig = true }
    packaging.resources.excludes += "/META-INF/{AL2.0,LGPL2.1}"
    packaging.jniLibs.useLegacyPackaging = true
    packaging.jniLibs.keepDebugSymbols += setOf(
        "**/liblitertlm_jni.so",
        "**/libonnxruntime.so",
        "**/libQnnHtp.so",
        "**/libQnnHtpPrepare.so",
        "**/libQnnHtpV73Skel.so",
        "**/libQnnHtpV73Stub.so",
        "**/libQnnSystem.so",
    )
    sourceSets["main"].jniLibs.srcDir("runtime-libs")
    if (nativeRuntimeEnabled) {
        externalNativeBuild.cmake {
            path = file("src/main/cpp/CMakeLists.txt")
            version = "3.22.1"
        }
    }

    testOptions {
        unitTests.isIncludeAndroidResources = true
    }

    lint {
        abortOnError = true
        warningsAsErrors = true
        disable += setOf("GradleDependency", "AndroidGradlePluginVersion", "ChromeOsAbiSupport")
    }
}

kotlin {
    compilerOptions { jvmTarget.set(JvmTarget.JVM_17) }
}

ksp { arg("room.schemaLocation", "$projectDir/schemas") }

val testNativePolicies by tasks.registering(Exec::class) {
    inputs.files("src/main/cpp/tensor_validation.h", "src/test/cpp/tensor_validation_test.cpp")
    outputs.file(layout.buildDirectory.file("native-policy-test/tensor_validation_test"))
    commandLine("bash", rootProject.file("tools/test_native_policies.sh"))
}
tasks.named("check").configure { dependsOn(testNativePolicies) }

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2024.12.01")
    implementation(composeBom)
    androidTestImplementation(composeBom)

    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.activity:activity-compose:1.10.0")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.navigation:navigation-compose:2.8.5")

    implementation("androidx.room:room-runtime:2.8.4")
    implementation("androidx.room:room-ktx:2.8.4")
    ksp("androidx.room:room-compiler:2.8.4")

    implementation("androidx.media3:media3-exoplayer:1.5.1")
    implementation("androidx.media3:media3-session:1.5.1")
    implementation("androidx.media3:media3-common:1.5.1")
    implementation("com.google.ai.edge.litertlm:litertlm-android:0.16.1")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")

    testImplementation("junit:junit:4.13.2")
    testImplementation("androidx.test:core:1.6.1")
    testImplementation("androidx.room:room-testing:2.8.4")
    testImplementation("org.robolectric:robolectric:4.14.1")
    testImplementation("org.json:json:20240303")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.9.0")

    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.6.1")
    androidTestImplementation("androidx.compose.ui:ui-test-junit4")
    debugImplementation("androidx.compose.ui:ui-tooling")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
}
