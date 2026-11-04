#!/bin/sh
# Build bridge/build/version.dll (32-bit) with MinGW-w64 from Linux/WSL:
#   sudo apt install g++-mingw-w64-i686
#   sh bridge/build.sh
# The result has no DLL dependencies besides Windows' own (static libgcc/libstdc++).
set -eu
cd "$(dirname "$0")"
CXX="${CXX:-i686-w64-mingw32-g++}"
mkdir -p build
"$CXX" -std=c++17 -O2 -shared -static -static-libgcc -static-libstdc++ -Wall -Wextra -Wno-cast-function-type \
    -o build/version.dll src/bridge.cpp version.def -Wl,--enable-stdcall-fixup -Wl,--kill-at
echo "built bridge/build/version.dll"
