plugins {
    id("com.android.application") version "8.5.0" apply false
    kotlin("android") version "1.9.24" apply false   // 升级 Kotlin
}

allprojects {
    repositories {
        google()
        mavenCentral()
    }
}

tasks.register("clean", Delete::class) {
    delete(rootProject.buildDir)
}
