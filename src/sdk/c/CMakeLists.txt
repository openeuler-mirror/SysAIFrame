cmake_minimum_required(VERSION 3.16)
project(sysai VERSION 0.1.0 LANGUAGES C)

# Options
option(BUILD_EXAMPLES "Build example programs" OFF)

# Find dependencies
find_package(PkgConfig REQUIRED)
pkg_check_modules(SYSTEMD REQUIRED libsystemd)
pkg_check_modules(CJSON REQUIRED libcjson)

# Library sources (use system libcjson, no bundled cJSON.c)
set(SYSAI_SOURCES
    src/sysai_client.c
    src/sysai_types.c
    src/sysai_streaming.c
)

# Create shared library
add_library(sysai SHARED ${SYSAI_SOURCES})

# Set library properties
set_target_properties(sysai PROPERTIES
    VERSION ${PROJECT_VERSION}
    SOVERSION 0
    PUBLIC_HEADER include/sysai.h
    C_STANDARD 11
    C_VISIBILITY_PRESET hidden
)

# Include directories
target_include_directories(sysai
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/src
        ${SYSTEMD_INCLUDE_DIRS}
        ${CJSON_INCLUDE_DIRS}
)

# Link libraries
target_link_libraries(sysai
    PRIVATE
        ${SYSTEMD_LIBRARIES}
        ${CJSON_LIBRARIES}
)

# Compiler flags
target_compile_options(sysai
    PRIVATE
        -Wall
        -Wextra
        -fvisibility=hidden
)

# Define SYSAI_BUILDING when building the library
target_compile_definitions(sysai PRIVATE SYSAI_BUILDING)

# Installation
include(GNUInstallDirs)

install(TARGETS sysai
    EXPORT sysai-targets
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    PUBLIC_HEADER DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
)

# Install pkg-config file
configure_file(sysai.pc.in sysai.pc @ONLY)
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/sysai.pc
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/pkgconfig
)

# Install CMake config files
install(EXPORT sysai-targets
    FILE sysai-targets.cmake
    NAMESPACE sysai::
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/sysai
)

configure_file(sysai-config.cmake.in sysai-config.cmake @ONLY)
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/sysai-config.cmake
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/sysai
)
