#!/bin/bash
set -x

vzpkg="$PKG"
# vzlinux-6
# vzlinux-7
vzplatform="$PLATFORM"
# apps or services
target="$TARGET"

test_package() {
/usr/bin/test_launcher.py -p $vzpkg $vzplatform $target
}

test_package
