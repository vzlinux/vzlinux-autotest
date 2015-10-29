%define git 20151020

Summary: Autotests for Virtuozzo Linux
Name: vzlinux-autotest
Version: 0
Release: 0.%{git}.4%{?dist}
License: GPLv2
Group: System Environment/Base
URL: https://git.sw.ru/projects/INT/repos/vzlinux-autotest/
Source0: %{name}-%{git}.tar.bz2
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root
Requires: python-lockfile
Requires: python-psutil
Requires: mock
BuildArch: noarch

%description
Autotests for Virtuozzo Linux.

%prep
%setup -qn %{name}-%{git}

%build

%install
rm -rf $RPM_BUILD_ROOT
mkdir -p $RPM_BUILD_ROOT%{_bindir}
install -m 0755 launcher.py $RPM_BUILD_ROOT%{_bindir}/launcher.py

mkdir -p $RPM_BUILD_ROOT%{_datadir}/vzlinux-autotest
install -m 0644 check_apps_in_chroot.py $RPM_BUILD_ROOT%{_datadir}/vzlinux-autotest/check_apps_in_chroot.py
install -m 0644 desktop-vl6.list $RPM_BUILD_ROOT%{_datadir}/vzlinux-autotest/vzlinux-6.desktop.list
install -m 0644 desktop-vl7.list $RPM_BUILD_ROOT%{_datadir}/vzlinux-autotest/vzlinux-7.desktop.list

mkdir -p $RPM_BUILD_ROOT%{_sysconfdir}/mock
cp mock/*.cfg $RPM_BUILD_ROOT%{_sysconfdir}/mock/

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root,-)
%{_bindir}/launcher.py
%{_datadir}/vzlinux-autotest
%{_sysconfdir}/mock/*.cfg
