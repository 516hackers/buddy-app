[app]
title = Buddy Assistant
package.name = buddyassistant
package.domain = org.buddyapp

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json

version = 1.0.0

# pyjnius and android have p4a built-in recipes — never version-pin them
# speech_recognition removed — no p4a recipe and no Android wheel
# python3/hostpython3 pinned to 3.11.9 — prevents 3.14 incompatibility with Kivy 2.3.0
requirements = python3==3.11.9,hostpython3==3.11.9,kivy==2.3.0,pyjnius,android,requests,urllib3,certifi,charset_normalizer,idna

orientation = portrait
fullscreen = 0

android.permissions = INTERNET,RECORD_AUDIO,VIBRATE,RECEIVE_BOOT_COMPLETED,FOREGROUND_SERVICE

android.api = 34
android.minapi = 21
android.ndk = 25b
android.ndk_api = 21
android.archs = arm64-v8a, armeabi-v7a

android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 1
