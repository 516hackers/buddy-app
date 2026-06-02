[app]

# (str) Title of your application
title = Buddy Assistant

# (str) Package name
package.name = buddyassistant

# (str) Package domain (needed for android/ios packaging)
package.domain = org.buddyapp

# (str) Source code directory
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,kv,atlas,ttf,txt

# (list) Requirements
# python3 pinned to 3.11.9 for compatibility
# pyjnius and android are built-in recipes
# No speech_recognition needed - using Android native speech
requirements = python3==3.11.9,hostpython3==3.11.9,kivy==2.3.0,pyjnius,android,requests,urllib3,certifi,charset_normalizer,idna

# (str) Supported orientation (one of landscape, sensorLandscape, portrait or all)
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# (list) Permissions
android.permissions = INTERNET,RECORD_AUDIO,VIBRATE,RECEIVE_BOOT_COMPLETED,FOREGROUND_SERVICE

# (int) Android API level to use
android.api = 34

# (int) Minimum API level
android.minapi = 21

# (str) Android NDK version
android.ndk = 25b

# (int) Android NDK API level to use
android.ndk_api = 21

# (list) Android architectures to build
android.archs = arm64-v8a, armeabi-v7a

# (bool) Allow backup of application data
android.allow_backup = True

# (str) Java classes to add
# android.add_src =

# (str) python-for-android branch to use
# p4a.branch = develop

# (list) Gradle dependencies to add
# android.gradle_dependencies =

# (bool) Enable or disable Androidx
android.enable_androidx = True

# (str) Android logcat filters to use
# android.logcat_filters =

# (bool) Copy prebuilt Python libraries (if any)
android.copy_libs = True

# (str) Android entry point (default is 'org.kivy.android.PythonActivity')
# android.entrypoint = org.kivy.android.PythonActivity

# (str) Android theme (default is '@android:style/Theme.NoTitleBar')
# android.theme = @android:style/Theme.NoTitleBar

# (str) Java source code directory
# android.java_src_dir =

# (list) Java files to add
# android.add_java =

# (list) Java jars to add
# android.add_jars =

# (list) Python modules to include (not needed for Android native)
# android.add_python_modules =

# (list) Python packages to include
# android.add_packages =

# (list) Python package data directories
# android.add_data_dir =

# (str) Presplash file (image to show before the app loads)
# presplash.filename = %(source.dir)s/presplash.png

# (str) Icon file (image for the app icon)
# icon.filename = %(source.dir)s/icon.png

# (str) Extra manifest arguments
# android.extra_manifest_xml =

# (str) Extra manifest application arguments
# android.extra_manifest_application_attributes =

# (str) Custom debug keystore (for signing APK)
# android.debug_keystore =

# (bool) Whether to include the Java support libraries
android.add_openssl = True

# (bool) Enable or disable the Android SQLite support
android.add_sqlite = True

# (list) Meta-data to add to the manifest
# android.meta_data =

# (list) Libraries to add to the APK
# android.add_libs =

# (str) P4A repo branch to use
# p4a.branch = master

# (str) P4A update URL
# p4a.update_url = https://github.com/kivy/python-for-android.git

# (bool) Enable build with Java code
# android.with_java = True

# (bool) Enable the Android support library
# android.use_support = False

# (str) Android SDK version to use
# android.sdk = 34

# (str) Android SDK directory
# android.sdk_path =

# (str) Android NDK directory
# android.ndk_path =

# (bool) Enable debugging
# android.debug = False

# (bool) Enable verbose build output
# android.verbose = False

# (str) Application version name (displayed to users)
version = 3.0.0

# (str) Application version code (internal, integer)
# android.version_code = 1

# (bool) Build with the Windows subsystem
# windows.subsystem = console

# (list) Windows dependencies
# windows.dependencies =

# (str) Windows hide console
# windows.hide_console = False

# (str) iOS bundle identifier
# ios.bundle_identifier = org.buddyapp.buddyassistant

# (str) iOS bundle name
# ios.bundle_name = Buddy Assistant

# (str) iOS bundle version
# ios.bundle_version = 1.0.0

# (str) iOS bundle version string (short)
# ios.bundle_version_short = 1.0

# (bool) Enable iOS automatic code signing
# ios.automatic_code_signing = False

# (str) iOS development team ID
# ios.development_team =

# (str) iOS provisioning profile UUID
# ios.provisioning_profile =

# (str) iOS code signing identity
# ios.code_sign_identity =

# (str) iOS entitlements file
# ios.entitlements_file =

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (bool) Warn when a distribution is being built from a non-repo branch
warn_on_root = 1

# (bool) Enable or disable the automatic Android APK signing
# android.sign = True

# (str) Path to a custom keystore for APK signing
# android.keystore =

# (str) Alias for the keystore
# android.keystore_alias =

# (str) Password for the keystore
# android.keystore_password =

# (str) Key password
# android.key_password =

# (str) Path to the Android SDK (auto-detected if not set)
# android.sdk_path =

# (str) Path to the Android NDK (auto-detected if not set)
# android.ndk_path =

# (str) Path to the Ant binary (auto-detected if not set)
# android.ant_path =

# (bool) Enable build in Docker
# buildozer.docker = False

# (str) Command to run for Docker
# buildozer.docker_cmd = docker

# (list) Additional command-line arguments for Docker
# buildozer.docker_args =

# (bool) Copy the application directory into the Docker container
# buildozer.docker_copy_app = True

# (str) Docker image to use
# buildozer.docker_image =

# (str) Path to the iOS SDK
# ios.sdk_path =

# (str) iOS Xcode version
# ios.xcode_version =

# (str) iOS deployment target
# ios.deployment_target = 9.0

# (bool) Use the iOS simulator
# ios.use_simulator = False
