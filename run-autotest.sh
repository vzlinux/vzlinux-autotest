#!/bin/bash
set -x

build_rpm() {
/usr/bin/test_launcher.py -p xterm vzlinux-7 apps
}

build_rpm
