plugins {
    id("com.android.application")
    kotlin("android")
}

android {
    namespace = "com.example.tvplayer"
    // 将 compileSdk 从 35 降到 34 来避免警告
    compileSdk = 34

    defaultConfig {
        applicationId = "com.example.tvplayer"
        minSdk = 23
        // targetSdk 也相应调整到 34
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"

        buildConfigField("String", "PLAYLIST_URL", "\"https://itv.19860519.xyz/output/tv.txt\"")
        buildConfigField("String", "PLAYLIST_URL_M3U", "\"https://itv.19860519.xyz/output/tv.m3u\"")
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
        debug {
            isMinifyEnabled = false
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
        compose = true
        buildConfig = true   // 关键修复：启用 BuildConfig 字段
    }

    composeOptions {
        kotlinCompilerExtensionVersion = "1.5.14"
    }
}

dependencies {
    implementation(platform("androidx.compose:compose-bom:2024.05.00"))
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.1")
    implementation("androidx.activity:activity-compose:1.9.1")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    // TV 组件
    implementation("androidx.tv:tv-material:1.0.0-alpha04")
    implementation("androidx.tv:tv-foundation:1.0.0-alpha04")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.1")
    implementation("androidx.navigation:navigation-compose:2.7.7")
    // Media3 ExoPlayer 播放器核心
    implementation("androidx.media3:media3-exoplayer:1.4.0")
    implementation("androidx.media3:media3-exoplayer-hls:1.4.0")
    implementation("androidx.media3:media3-ui:1.4.0")
    implementation("androidx.media3:media3-session:1.4.0")
    // 网络请求
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")
    // 协程
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
    // 调试工具
    debugImplementation("androidx.compose.ui:ui-tooling")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
    // DataStore
    implementation("androidx.datastore:datastore-preferences:1.1.1")
}
