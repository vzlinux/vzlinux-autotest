#!/usr/bin/python3

# Copyright (c) 2017-2021, Virtuozzo International GmbH
#
# Our contact details: Virtuozzo International GmbH, Vordergasse 59, 8200
# Schaffhausen, Switzerland.

import subprocess
import argparse
import sys
import tempfile
import os
import time
import shutil
from lockfile import LockFile, LockTimeout

def init_chroot(target):
    try:
        subprocess.call(['sudo', 'mock', '-r', target + '-autotest-x86_64',
                                 '--init'])
        # For 6.x / 7.x tests can be launched in chroot created by 8.x mock/rpm,
        # rebuild rpm db by means of native rpm
        if target == "vzlinux-6" or target == "vzlinux-7":
            subprocess.call(['sudo', 'mock', '-r', target + '-autotest-x86_64',
                                     '--chroot', 'rm -f /var/lib/rpm/__*'])
            subprocess.call(['sudo', 'mock', '-r', target + '-autotest-x86_64',
                                     '--chroot', 'rpm --rebuilddb'])
        subprocess.call(['sudo', 'mount', '-o', 'bind', '/proc',
                                 '/var/lib/mock/' + target + '-autotest-x86_64/root/proc'])
    except:
        print("mock failed to initialize chroot, probably incorrect target name")
        sys.exit(1)

def run_app_tests(target, pkgs_list):
    # Prepare a folder for logs
    subprocess.call(['sudo', 'mkdir', "-m777", "/var/log/vzlinux-autotests/"])

    subprocess.call(['sudo', 'cp', '/usr/share/vzlinux-autotest/check_apps_in_chroot.py',
                             '/var/lib/mock/' + target + '-autotest-x86_64/root/root'])

    f = open(pkgs_list, 'r')
    for pkg in f.readlines():
    #    subprocess.call(['sudo', 'cp', pkgs_list,
    #                             '/var/lib/mock/' + target + '-autotest-x86_64/root/root/list'])
        pkg_file = open('/var/lib/mock/' + target + '-autotest-x86_64/root/tmp/list', 'w')
        pkg_file.write(pkg)
        pkg_file.close()
        subprocess.call(['sudo', 'chroot', '/var/lib/mock/' + target + '-autotest-x86_64/root',
                                 'python', 'root/check_apps_in_chroot.py', 'tmp/list'])

        # Copy results to /var/log
        result_dir = "/var/log/vzlinux-autotests/" + target + "/" + pkg.rstrip()
        if os.path.exists(result_dir):
            shutil.rmtree(result_dir)
        testdir = '/var/lib/mock/' + target + '-autotest-x86_64/root/tmp/results'
        shutil.copytree(testdir, result_dir)

        # Kill orphans - that's why we call check_apps_in_chroot.py per every package, not
        # per all packages at once. Orphans will be killed after each package test and won't
        # occupy too many resources
        subprocess.call(['sudo', 'mock', '-r', target + '-autotest-x86_64',
                                 '--orphanskill'])
        # We have to remount /proc after orpahskill
        subprocess.call(['sudo', 'mount', '-o', 'bind', '/proc',
                                 '/var/lib/mock/' + target + '-autotest-x86_64/root/proc'])
        subprocess.call(['sudo', 'mount', '-o', 'bind', '/dev',
                                 '/var/lib/mock/' + target + '-autotest-x86_64/root/dev'])
        # mount /dev/shm too
        subprocess.call(['sudo', 'mount', '-o', 'bind', '/dev/shm',
                                 '/var/lib/mock/' + target + '-autotest-x86_64/root/dev/shm'])
        # need to mount /dev/pts if we still want to use sudo in chroot
        subprocess.call(['sudo', 'mount', '-o', 'bind', '/dev/pts',
                                 '/var/lib/mock/' + target + '-autotest-x86_64/root/dev/pts'])

def run_service_tests(target, pkgs_list):
    subprocess.call(['python', '/usr/share/vzlinux-autotest/check_services_in_vm.py', pkgs_list])

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="VzLinux Autotest Launcher")
    parser.add_argument('target', action='store', choices=['vzlinux-6', 'vzlinux-7', 'vzlinux-8'])
    parser.add_argument('mode', action='store', choices=['apps','services'])
    parser.add_argument('-t', '--timeout', action='store', nargs='?',
                               help='Maximum time in seconds to wait for an exclusive lock '\
                                    'on a test chroot')
    parser.add_argument('-p', '--pkg', action='append',
                               help='Check only package with given name. This option can ' \
                                    'be specified more than once. By default, all packages ' \
                                    'from the autotest list are checked.')
    cmdline = parser.parse_args(sys.argv[1:])

    lock_name = "/tmp/vzlinux-autotest-" + cmdline.target
    chroot_timeout = 60
    if cmdline.timeout:
        chroot_timeout = cmdline.timeout

    lock = LockFile(lock_name)
    try:
        print("Acquiring lock for '%s' chroot" % cmdline.target)
        lock.acquire(timeout=chroot_timeout)    # wait up to 60 seconds
    except LockTimeout:
        print('Cannot acquire lock, likely another instance of a test is already running. '
              'If this is not the case, please remove lock file "%s" manually.' % lock_name)
        sys.exit(1)

    # Form list of packages to be processed - checkers takes file with package list
    if cmdline.pkg:
        (ftmp, pkg_list) = tempfile.mkstemp()
        for p in cmdline.pkg:
            os.write(ftmp, p + "\n")
        os.close(ftmp)
    elif cmdline.mode == 'apps':
        pkg_list = '/usr/share/vzlinux-autotest/' + cmdline.target + '.desktop.list'
    elif cmdline.mode == 'services':
        pkg_list = '/usr/share/vzlinux-autotest/' + cmdline.target + '.service.list'

    if cmdline.mode == 'apps':
        init_chroot(cmdline.target)
        run_app_tests(cmdline.target, pkg_list)
        subprocess.call(['sudo', 'mock', '-r', cmdline.target + '-autotest-x86_64',
                                 '--orphanskill'])
        subprocess.call(['sudo', 'umount',
                                 '/var/lib/mock/' + cmdline.target + '-autotest-x86_64/root/proc'])
        subprocess.call(['sudo', 'umount',
                                 '/var/lib/mock/' + cmdline.target + '-autotest-x86_64/root/dev'])
        subprocess.call(['sudo', 'umount',
                                 '/var/lib/mock/' + cmdline.target + '-autotest-x86_64/root/dev/shm'])
        subprocess.call(['sudo', 'umount',
                                 '/var/lib/mock/' + cmdline.target + '-autotest-x86_64/root/dev/pts'])
    elif cmdline.mode == 'services':
        run_service_tests(cmdline.target, pkg_list)

    # Cleanup
    if cmdline.pkg:
        os.remove(pkg_list)

    lock.release()
