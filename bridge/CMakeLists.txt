# Build with Visual Studio (x86): cmake -S bridge -B bridge/build -A Win32 && cmake --build bridge/build --config Release
cmake_minimum_required(VERSION 3.21)
project(K2APBridge CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded")
add_library(version SHARED src/bridge.cpp version.msvc.def)
target_compile_definitions(version PRIVATE _CRT_SECURE_NO_WARNINGS WIN32_LEAN_AND_MEAN NOMINMAX)
