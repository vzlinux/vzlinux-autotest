#!/bin/bash

vzpkg="$@"
# vzlinux-6
# vzlinux-7
vzplatform="$PLATFORM"
# apps or services
target="$TARGET"

test_package() {
cd
echo "$vzpkg" >> $HOME/pkg_list
/usr/share/vzlinux-autotest/check_services_in_vm.py $HOME/pkg_list
}

test_package
