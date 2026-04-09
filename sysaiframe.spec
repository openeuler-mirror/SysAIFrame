%define _empty_manifest_terminate_build 0
# Disable debuginfo generation for pure Python packages
%undefine _find_debuginfo_dwz_opts
%define _find_debuginfo_opts -g
%define debug_package %{nil}
Name:    sysaiframe
Version: 1.0.0
Release: 1
Summary: CTyunOS System AI Framework Gateway
License: MulanPSL-2.0
URL:     https://gitee.com/openeuler/SysAIFrame
Source0: %{name}-%{version}.tar.gz

BuildRequires: python3-devel
BuildRequires: python3-setuptools
BuildRequires: python3-pip
BuildRequires: cmake >= 3.16
BuildRequires: gcc
BuildRequires: systemd-devel
BuildRequires: cjson-devel

Requires: python3 >= 3.8
Requires: python3-pydantic >= 1.10.0
Requires: python3-httpx >= 0.25.0
Requires: python3-pyyaml >= 6.0.1
Requires: python3-ruamel-yaml >= 0.18.0
Requires: python3-click >= 8.1.0
Requires: python3-anyio >= 3.6.0
Requires: python3-h11 >= 0.8
Requires: python3-sniffio >= 1.0
Requires: python3-typing-extensions >= 4.0
Requires: python3-websockets >= 10.0
Requires: python3-watchfiles >= 0.13
Requires: systemd
Requires: dbus-daemon

%description
CTyunOS System AI Framework Gateway - Unified AI service gateway with
OpenAI-compatible API, D-Bus interface, and service discovery capabilities.

%package devel
Summary: C/C++ development files for SysAIFrame AI Gateway
Requires: %{name} = %{version}-%{release}
Requires: systemd-libs
Requires: cjson

%description devel
C/C++ client library (libsysai.so) and header files for developing
applications that communicate with SysAIFrame AI Gateway via D-Bus.

%package python-devel
Summary: Python development library for SysAIFrame AI Gateway
Requires: %{name} = %{version}-%{release}
Requires: python3-dbus
Requires: python3-gobject

%description python-devel
Python client library (sysai) for developing applications that
communicate with SysAIFrame AI Gateway via D-Bus.

%package rust-devel
Summary: Rust development library for SysAIFrame AI Gateway

%description rust-devel
Rust SDK source (sysai-sdk crate) for developing applications that
communicate with SysAIFrame AI Gateway via D-Bus.

%prep
%autosetup -n %{name}-%{version} -p1
# Move src contents to top level for build
mv src/* src/.[!.]* . 2>/dev/null || true
rmdir src

%build
# Build main package using RPM standard macro
%py3_build

# Build C SDK
mkdir -p sdk/c/build && cd sdk/c/build
cmake .. -DCMAKE_INSTALL_PREFIX=%{_prefix} \
         -DCMAKE_INSTALL_LIBDIR=%{_libdir} \
         -DBUILD_EXAMPLES=OFF
make %{?_smp_mflags}
cd ../../..

%install
# Install main package using RPM standard macro
%py3_install

# Install C SDK
cd sdk/c/build
make install DESTDIR=%{buildroot}
cd ../../..

# Install Python SDK
cd sdk/python
%{__python3} -m pip install --no-deps --root=%{buildroot} --prefix=%{_prefix} .
cd ../..

# Install Rust SDK source
install -d -m 0755 %{buildroot}%{_datadir}/sysaiframe/rust-sdk
cp -a sdk/rust/src %{buildroot}%{_datadir}/sysaiframe/rust-sdk/
cp sdk/rust/Cargo.toml %{buildroot}%{_datadir}/sysaiframe/rust-sdk/
