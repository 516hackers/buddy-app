[app]
title            = Buddy Assistant
package.name     = buddyassistant
package.domain   = org.buddy

source.dir       = .
source.include_exts = py,png,jpg,kv,atlas,json

version = 2.0

requirements = python3,kivy==2.3.0,pyjnius,speechrecognition,requests,urllib3,certifi,charset-normalizer,idna,audioread,pyaudio

orientation  = portrait
fullscreen   = 0

android.permissions = INTERNET,RECORD_AUDIO,MODIFY_AUDIO_SETTINGS,READ_PHONE_STATE,CHANGE_AUDIO_SETTINGS,FOREGROUND_SERVICE,WAKE_LOCK

android.api    = 34
android.minapi = 24
android.ndk    = 25b

android.accept_sdk_license = True
android.archs  = arm64-v8a

android.features = android.hardware.microphone

p4a.branch = master

log_level = 2

[buildozer]
log_level    = 2
warn_on_root = 1
