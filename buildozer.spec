[app]
# 应用信息
title = 星迹日历
package.name = xingjirili
package.domain = org.xingji

# 源码
source.dir = .
source.include_exts = py,png,jpg,jpeg,otf,ttf
source.include_patterns = assets/*,images/*

# 版本
version = 0.1.0

# 依赖库（纯Python，无需编译C++）
requirements = python3,kivy==2.3.1,lunar_python,plyer

# 界面方向：竖屏
orientation = portrait

# 全屏
fullscreen = 0

# 图标与启动图（使用你自制的星空图标）
icon.filename = app_icon.png
presplash.filename = app_icon.png

# 支持的手机架构（arm64-v8a 覆盖几乎所有现代安卓手机）
android.archs = arm64-v8a

# 安卓权限：通知弹窗 + 读取手机图片
android.permissions = VIBRATE,POST_NOTIFICATIONS,READ_MEDIA_IMAGES,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE

# 安卓API级别（对应安卓版本兼容性）
android.api = 34
android.minapi = 24

# 应用名称显示为中文
android.app_name = 星迹日历

# 日志级别
log_level = 2

[buildozer]
log_level = 2
warn_on_root = 1
