[app]
# (str) Title of your application
title = Cycling Coach

# (str) Package name
package.name = cyclingcoach

# (str) Package domain (needed for android/ios packaging)
package.domain = com.coachapp

# (str) Source code where the main.py lives
source.dir = .

# (list) Source files to include
source.include_exts = py,png,jpg,kv,atlas,json


# (list) List of inclusions using pattern matching
source.include_patterns = model_xgb.json,model_config.json,coach_engine.py


# (str) Application versioning
version = 0.1

# (list) Application requirements
# Separate requirements with commas
requirements = python3,kivy==2.3.0,pillow,numpy,pandas,joblib


# (str) Custom source folders for requirements
# Sets custom source for any requirements with source
# requirements.source.mymodule = ../../mymodule

# (str) Presplash of the application
#presplash.filename = %(source.dir)s/data/presplash.png

# (str) Icon of the application
#icon.filename = %(source.dir)s/data/icon.png

# (str) Supported orientation (landscape, sensorLandscape, portrait or all)
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# (string) Presplash background color (for android toolchain)
# Supported formats are: #RRGGBB #AARRGGBB or one of the following names:
# red, blue, green, black, white, gray, cyan, magenta, yellow, lightgray,
# darkgray, grey, lightgrey, darkgrey, aqua, fuchsia, lime, maroon, navy,
# olive, purple, silver, teal.
android.presplash_color = #0D1117

# (list) Permissions
android.permissions = android.permission.INTERNET,android.permission.WRITE_EXTERNAL_STORAGE

# (bool) Automatically accept Android SDK licenses
android.accept_sdk_license = True

# (int) Target Android API, should be as high as possible.
android.api = 33

# (int) Minimum API your APK / AAB will support.
android.minapi = 24

# (int) Android SDK version to use
android.sdk = 33

# (str) Android NDK version to use
android.ndk = 25b

# (bool) Use --private data storage (True) or --dir public storage (False)
android.private_storage = True

# (str) Android NDK directory (if empty, it will be automatically downloaded.)
#android.ndk_path =

# (str) Android SDK directory (if empty, it will be automatically downloaded.)
#android.sdk_path =

# (str) python-for-android fork to use, defaults to upstream but can be
# - develop
# - master
# or a git URL which will be used to download p4a.
#p4a.fork = upstream

# (str) git branch/tag/commit from p4a to use
p4a.branch = v2024.01.21

# (str) Bootstrap to use for p4a
p4a.bootstrap = sdl2

# (int) port number to specify an explicit --port= p4a argument (eg. 8090)
#p4a.port =

# (str) The android arch to build for, choices: armeabi-v7a, arm64-v8a, x86, x86_64
# In past, was `android.arch` as we weren't supporting builds for multiple archs at the same time.
android.archs = arm64-v8a, armeabi-v7a

# (bool) enables Android auto backup feature (Android API >=23)
android.allow_backup = True

[buildozer]
# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 1

# (str) Path to build artifact storage, absolute or relative to spec file
#build_dir = ./.buildozer

# (str) Path to build output (i.e. .apk, .aab, .ipa) storage
#bin_dir = ./bin
