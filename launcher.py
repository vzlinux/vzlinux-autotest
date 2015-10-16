#!/usr/bin/python

import subprocess
import argparse
import sys
import tempfile
import os

def init_chroot(target):
    try:
        subprocess.call(['sudo', 'mock', '-r', target + '-autotest-x86_64',
                                 '--init'])
        subprocess.call(['sudo', 'mount', '-o', 'bind', '/proc',
                                 '/var/lib/mock/' + target + '-autotest-x86_64/root/proc'])
    except:
        print("mock failed to initializae chroot, probably incorrect target name")
        sys.exit(1)

def run_app_tests(target, pkgs_list):
    subprocess.call(['sudo', 'cp', '/usr/share/vzlinux-autotest/check_apps_in_chroot.py',
                             '/var/lib/mock/' + target + '-autotest-x86_64/root/root'])
    subprocess.call(['sudo', 'cp', pkgs_list,
                             '/var/lib/mock/' + target + '-autotest-x86_64/root/root/list'])
    subprocess.call(['sudo', 'chroot', '/var/lib/mock/' + target + '-autotest-x86_64/root',
                             'python', 'root/check_apps_in_chroot.py', 'root/list'])

def run_service_tests(target, pkgs_list):
    subprocess.call(['sudo', 'cp', '/usr/share/vzlinux-autotest/check_services_in_chroot.py',
                             '/var/lib/mock/' + target + '-autotest-x86_64/root/root'])
    subprocess.call(['sudo', 'cp', pkgs_list,
                             '/var/lib/mock/' + target + '-autotest-x86_64/root/root/list'])
    subprocess.call(['sudo', 'chroot', '/var/lib/mock/' + target + '-autotest-x86_64/root',
                             'python', 'root/check_services_in_chroot.py', 'root/list'])

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="VzLinux Autotest Launcher")
    parser.add_argument('target', action='store', choices=['vzlinux-6', 'vzlinux-7'])
    parser.add_argument('mode', action='store', choices=['apps','services'])
    parser.add_argument('-p', '--pkg', action='append',
                               help='Check only package with given name. This option can ' \
                                    'be specified more than once. By default, all packages ' \
                                    'from the autotest list are checked.')
    cmdline = parser.parse_args(sys.argv[1:])

    # Form list of packages to be processed - checkers takes file with package list
    if cmdline.pkg:
        (ftmp, pkg_list) = tempfile.mkstemp()
        for p in cmdline.pkg:
            os.write(ftmp, p + "\n")
        os.close(ftmp)
    elif cmdline.mode == 'apps':
        pkg_list = '/usr/share/vzlinux-autotest/' + target + 'desktop.list'
    elif cmdline.mode == 'services':
        pkg_list = '/usr/share/vzlinux-autotest/' + target + 'service.list'

    init_chroot(cmdline.target)

    if cmdline.mode == 'apps':
        run_app_tests(cmdline.target, pkg_list)
    elif cmdline.mode == 'services':
        run_service_tests(cmdline.target, pkg_list)

    # Cleanup
    if cmdline.pkg:
        os.remove(pkg_list)

