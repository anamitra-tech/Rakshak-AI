import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// SARVAM_API_KEY already exists server-side in the repo root .env for the
// Python webhook, but Android builds don't read .env -- this is a separate,
// per-machine copy in local.properties (gitignored, never committed), same
// posture as sdk.dir. (Google Cloud Vision was considered for the OCR cloud
// fallback and rejected -- needs a billing account, unavailable for this
// project -- so there's no equivalent key here for that; see
// ocr/CloudOcrClient.kt, which calls Prahari's own self-hosted Tesseract
// endpoint instead.)
val localProperties = Properties().apply {
    val f = rootProject.file("local.properties")
    if (f.exists()) f.inputStream().use { load(it) }
}
val sarvamApiKey: String = localProperties.getProperty("SARVAM_API_KEY", "")

android {
    namespace = "com.rakshak.ai"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.rakshak.ai"
        minSdk = 29
        targetSdk = 34
        versionCode = 1
        versionName = "0.1.0-phase1"
        buildConfigField("String", "SARVAM_API_KEY", "\"$sarvamApiKey\"")
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        viewBinding = true
        buildConfig = true
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.6.1")
    implementation("com.google.android.material:material:1.12.0")
    implementation("androidx.constraintlayout:constraintlayout:2.1.4")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.7.0")
    implementation("androidx.activity:activity-ktx:1.8.2")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")
    // Missed-escalation evidence delivery: the 2-minute Tier-2 ack timeout
    // needs to survive the triggering Activity finishing (or the process
    // dying) — WorkManager is the standard, permission-free way to schedule
    // deferred work that survives both.
    implementation("androidx.work:work-runtime-ktx:2.9.1")
    // On-device language identification, used to auto-select the matching
    // TTS voice for the warning speech (see tts/SpeechLanguageSelector.kt).
    // The model ships bundled in the AAR -- no download, no network call, no
    // text ever leaves the device for this.
    implementation("com.google.mlkit:language-id:17.0.6")
    // On-device OCR for the "Upload screenshot" option on the "Check a
    // call/message" screen (see ocr/ScreenshotOcrHelper.kt) -- Latin script,
    // same bundled-model/no-network posture as language-id above.
    implementation("com.google.mlkit:text-recognition:16.0.1")
    // Devanagari-script OCR (Hindi, Marathi) -- ML Kit v2 ships script
    // recognizers as separate artifacts; this is NOT covered by the Latin
    // artifact above. Still no coverage for Bengali/Tamil/Telugu/Kannada/
    // Malayalam/Gujarati/Punjabi/Odia/Urdu scripts -- ML Kit has no artifact
    // for any of those at all (only Latin/Chinese/Devanagari/Japanese/Korean
    // exist), see ocr/CloudOcrClient.kt for the online fallback.
    implementation("com.google.mlkit:text-recognition-devanagari:16.0.1")
}
