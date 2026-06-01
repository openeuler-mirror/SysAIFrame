%define _empty_manifest_terminate_build 0
# Disable debuginfo generation for pure Python packages
%undefine _find_debuginfo_dwz_opts
%define _find_debuginfo_opts -g
%define debug_package %{nil}
Name:    sysaiframe
Version: 1.1.0
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

# Register package is not ready yet, commented out for now
#%package register
#Summary: AI Model Registration Service for SysAIFrame
#Requires: python3 >= 3.8
#Requires: python3-pyyaml >= 6.0.1
#Requires: python3-click >= 8.1.0
#
#%description register
#Independent package for model registration using mDNS/DNS-SD.

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

# Register package is not ready yet, commented out for now
# Build register package
#cd sysai-register
#%py3_build
#cd ..

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

# Register package is not ready yet, commented out for now
# Install register package
#cd sysai-register
#%py3_install
#cd ..

# Install bundled wheel dependencies from wheels/ directory in source
%{__python3} -m pip install --no-deps --no-index --find-links=%{_builddir}/%{name}-%{version}/wheels \
    --target=%{buildroot}%{python3_sitelib} \
    fastapi starlette uvicorn python-multipart annotated-doc

# Install configuration files
install -d -m 0755 %{buildroot}%{_sysconfdir}/sysaiframe
install -m 0644 config/models.yaml.example %{buildroot}%{_sysconfdir}/sysaiframe/models.yaml.example

# Install D-Bus configuration
install -d -m 0755 %{buildroot}%{_sysconfdir}/dbus-1/system.d
install -m 0644 dbus/sysaiframe.conf %{buildroot}%{_sysconfdir}/dbus-1/system.d/sysaiframe.conf

# Install systemd service
install -d -m 0755 %{buildroot}%{_unitdir}
install -m 0644 systemd/sysaiframe.service %{buildroot}%{_unitdir}/sysaiframe.service

# Create directories
install -d -m 0755 %{buildroot}/var/log/sysaiframe
install -d -m 0755 %{buildroot}/opt/sysaiframe

%post
# Create working directory
if [ ! -d /opt/sysaiframe ]; then
    mkdir -p /opt/sysaiframe
    chmod 755 /opt/sysaiframe
fi

# Note: Configuration file (models.yaml) will be automatically created by the service
# on first startup with empty configuration. Do not copy from example file.

# Ensure configuration directory has correct permissions
chmod 755 %{_sysconfdir}/sysaiframe

# Ensure log directory has correct permissions
# Log directory permissions are set during installation

# Reload D-Bus configuration
systemctl daemon-reload >/dev/null 2>&1 || :
if [ -f %{_sysconfdir}/dbus-1/system.d/sysaiframe.conf ]; then
    systemctl reload dbus >/dev/null 2>&1 || :
fi

# Enable service
systemctl enable sysaiframe.service >/dev/null 2>&1 || :

# Start service automatically
# $1 == 1: First installation, start service
if [ $1 -eq 1 ]; then
    systemctl start sysaiframe.service >/dev/null 2>&1 || :
fi

# $1 >= 2: Upgrade, restart if running, otherwise start
if [ $1 -ge 2 ]; then
    if systemctl is-active --quiet sysaiframe.service; then
        systemctl restart sysaiframe.service >/dev/null 2>&1 || :
    else
        systemctl start sysaiframe.service >/dev/null 2>&1 || :
    fi
fi

%preun
# Stop service before uninstall
if [ $1 -eq 0 ]; then
    systemctl stop sysaiframe.service >/dev/null 2>&1 || :
    systemctl disable sysaiframe.service >/dev/null 2>&1 || :
fi

%postun
# Reload D-Bus configuration after uninstall
if [ $1 -eq 0 ]; then
    systemctl daemon-reload >/dev/null 2>&1 || :
    systemctl reload dbus >/dev/null 2>&1 || :
fi

%files
%defattr(-,root,root,-)
%{python3_sitelib}/sysai_framework/
%{python3_sitelib}/build/lib/sysai_framework/
%{python3_sitelib}/sysai_framework-*.egg-info/
# Bundled dependencies
%{python3_sitelib}/fastapi/
%{python3_sitelib}/fastapi-*.dist-info/
%{python3_sitelib}/bin/fastapi
%{python3_sitelib}/starlette/
%{python3_sitelib}/starlette-*.dist-info/
%{python3_sitelib}/uvicorn/
%{python3_sitelib}/uvicorn-*.dist-info/
%{python3_sitelib}/bin/uvicorn
%{python3_sitelib}/python_multipart/
%{python3_sitelib}/python_multipart-*.dist-info/
%{python3_sitelib}/multipart/
%{python3_sitelib}/annotated_doc/
%{python3_sitelib}/annotated_doc-*.dist-info/
# Register package is not ready yet, commented out for now
#%{python3_sitelib}/sysai-register/
%{_bindir}/ai-config
%{_bindir}/ai-discover
%config(noreplace) %{_sysconfdir}/sysaiframe/models.yaml.example
%config(noreplace) %{_sysconfdir}/dbus-1/system.d/sysaiframe.conf
%config(noreplace) %{_unitdir}/sysaiframe.service
%dir %attr(0755,root,root) /opt/sysaiframe
%dir %attr(0755,root,root) /var/log/sysaiframe

%files devel
%defattr(-,root,root,-)
%{_libdir}/libsysai.so*
%{_includedir}/sysai.h
%{_libdir}/pkgconfig/sysai.pc
%{_libdir}/cmake/sysai/

%files python-devel
%defattr(-,root,root,-)
%{python3_sitelib}/sysai/
%{python3_sitelib}/sysai-*.dist-info/

%files rust-devel
%defattr(-,root,root,-)
%{_datadir}/sysaiframe/rust-sdk/

# Register package is not ready yet, commented out for now
#%files register
#%defattr(-,root,root,-)
#%{python3_sitelib}/sysai_register/
#%{python3_sitelib}/sysai_register-*.dist-info/
#%{_bindir}/sysai-register

%changelog
* Sun Nov 23 2025 SysAIFrame Team <sysaiframe@ctyunos.com> - 1.0.0-1
- Initial release of SysAIFrame Gateway

