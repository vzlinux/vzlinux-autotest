#!/bin/bash
set -x

vzpkg="$PKG"
# vzlinux-6
# vzlinux-7
vzplatform="$PLATFORM"
# apps or services
target="$TARGET"

test_package() {
#/usr/bin/test_launcher.py -p $vzpkg $vzplatform $target
# go to the root of home dir
cd
echo "$vzpkg" >> $HOME/pkg_list
/usr/share/vzlinux-autotest/check_apps_in_chroot.py $HOME/pkg_list
}

test_package
