## termux系统库安装
```shell script
pkg install -y android-tools cmake libandroid-spawn build-essential cmake clang binutils autoconf automake libtool pkg-config libjpeg-turbo libxml2 libxslt libpng libwebp ninja which libllvm git wget vim rust mount-utils
pkg install -y openblas libopenblas 
# 在https://tur.kcubeterm.com tur-packages/tur aarch64 openblas aarch64 0.3.21-1 下可以安装openblas

export CXXFLAGS="-fuse-ld=lld"
export LDFLAGS="-fuse-ld=lld"

# 系统已经安装cmake
export CMAKE_PREFIX_PATH=/data/data/com.termux/files/usr
export PATH=$PATH:/data/data/com.termux/files/usr/bin

```

## 标准安装
```shell script
pip install -r requirements.txt
```


## ua2安装
进入data/uiautomator2-2.16.25
```shell script
python setup.py install
```


## android SDK安装
```shell script

# jdk安装
pkg install openjdk-17

# 创建 SDK 目录
mkdir -p ~/android/sdk
cd ~/android/sdk

# 下载最新版 commandlinetools
wget https://googledownloads.cn/android/repository/commandlinetools-linux-11076708_latest.zip

# 解压并调整目录结构
unzip commandlinetools-linux-*.zip -d cmdline-tools
mv cmdline-tools/cmdline-tools cmdline-tools/latest

# 设置环境变量
vim ~/.bashrc
export ANDROID_HOME=$HOME/android/sdk
export PATH=$PATH:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools
export ANDROID_SDK_TOOLS=$ANDROID_HOME/cmdline-tools/latest
export JAVA_HOME=/data/data/com.termux/files/usr/lib/jvm/java-17-openjdk
export PATH=$JAVA_HOME/bin:$PATH

. ~/.barshrc





$ANDROID_SDK_TOOLS/bin/sdkmanager --licenses

# 使用sdkmanager升级SDK工具
$ANDROID_SDK_TOOLS/bin/sdkmanager --update

# 安装指定版本（如果更新后仍不满足，可尝试安装明确版本）
$ANDROID_SDK_TOOLS/bin/sdkmanager "cmdline-tools;latest"

$ANDROID_SDK_TOOLS/bin/sdkmanager "build-tools;34.0.0"
```





## opencv安装
### 方法一: 标准库安装
```shell script
pkg install 
```
pkg install x11-repo
pkg install opencv-python

```shell script





# 参数说明：

# -DBUILD_ANDROID_EXAMPLES=OFF：禁用 Android 示例构建（解决当前报错的核心）
# -DBUILD_EXAMPLES=OFF：禁用所有示例构建（加快编译速度
# 安装时指定CMake参数，排除Android相关目标
CMAKE_ARGS="-DBUILD_ANDROID_EXAMPLES=OFF -DBUILD_EXAMPLES=OFF" pip install opencv-python

pip install scikit-build==0.18.1
pip install opencv-python==4.10.0.82 --no-build-isolation
export CMAKE_MAKE_PROGRAM=$(which ninja)
ln -s $PREFIX/lib/libjpeg.so $PREFIX/lib/libjpeg.so.8 2>/dev/null
ln -s $PREFIX/lib/libpng.so $PREFIX/lib/libpng.so.16 2>/dev/null

# 1. 设置环境变量禁用 Android 检测
mkdir ~/tmp
mkdir ~/tmp/build-tools
export ANDROID=~/tmp
export ANDROID_ABI=~/tmp
export ANDROID_NATIVE_API_LEVEL=~/tmp
export ANDROID_SDK=~/tmp
export ANDROID_SDK_ROOT=~/tmp
export ANDROID_HOME=~/tmp


export ANDROID_SDK_BUILD_TOOLS_VERSION= 
export ANDROID_SDK_BUILD_TOOLS_SUBDIR=~/tmp
export ANDROID_SDK_BUILD_TOOLS=~/tmp


# 2. 强制指定构建类型为 Unix
export CMAKE_ARGS="-D__ANDROID__=OFF -DANDROID=OFF"

pip install --no-build-isolation --config-settings=cmake.define.ANDROID=OFF --config-settings=cmake.define.__ANDROID__=OFF opencv-python==4.10.0.82
```


