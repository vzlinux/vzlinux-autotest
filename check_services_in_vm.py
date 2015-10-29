#!/usr/bin/env python

# Should be executed as a regular user (not root), see Readme.txt for more
# information.
#
# Usage:
#       python check_services_in_vm.py <packages_list_file>
#
# <packages_list_file> file should contain names of the packages (without
# versions, etc.) from the repositories to be processed.
# For simplicity, all currently enabled repositories will be used when
# installing the packages.
#
# The results will be available in the appropriate files in 'results'
# subdirectory of the current directory, see RES_* below.
# Each '*.list' file contains the list of packages of the particular kind.

import os.path
import os
import subprocess
import re
import sys
import shutil
import psutil

from datetime import datetime


# Regexp for the needed paths to the .service files.
re_service = re.compile('.*/lib/systemd/system/[^/]*[^@]\\.service')

SEP = 72 * '='

# The directory with the results
RESULT_DIR = '/tmp/results'

# Files with package lists of the given kind.
RES_FAILED_TO_INSTALL = RESULT_DIR + '/failed-to-install.list'
RES_FAILED_TO_REMOVE = RESULT_DIR + '/failed-to-remove.list'
RES_FAILED_TO_CHECK = RESULT_DIR + '/failed-to-check.list'
RES_FAILED = RESULT_DIR + '/failed.list'
RES_SUCCEEDED = RESULT_DIR + '/succeeded.list'
RES_SKIPPED = RESULT_DIR + '/skipped.list'


STATUS_ACTIVE = 'active'
STATUS_INACTIVE = 'inactive'
STATUS_FAILED = 'failed'


class SyncedOut(object):
    '''A wrapper around sys.stdout that flushes the output each time.

    May be used for logging, if 'logger' facilities from the standard
    library are not desirable.

    'orig_out' - the original stream to output to.

    Note that the class does not replace sys.stdout itself, it is the
    caller's responsibility.
    '''
    def __init__(self, orig_out):
        self.orig_out = orig_out

    def write(self, s):
        self.orig_out.flush()
        self.orig_out.write(s)
        self.orig_out.flush()


def mem_to_str(val, delta=False):
    '''Convert the number (amount of memory in bytes) to a string.

    The string corresponds to that amount of memory but in megabytes.
    '''
    if delta:
        fmt = '%+.2fM'
    else:
        fmt = '%.2fM'

    return fmt % (float(val) / (1024 * 1024))


def add_to_list(pkgname, fname):
    '''Add the given package name to the given file.'''
    with open(fname, 'a') as f:
        f.write(pkgname + '\n')


def get_installed_list():
    '''Returns the list of installed packages as a set.'''
    out = subprocess.check_output(
        ['sudo', 'rpm', '-q', '-a', '--queryformat', '%{NAME}\n'])
    return set(out.split('\n'))


def check_services(pkg, pkg_log):
    '''Check the services from the given package.

    Returns True if all the services have been checked successfully or the
    package contains no appropriate .service files and is therefore skipped.
    False is returned otherwise.

    'pkg' - name of the package.
    'pkg_log' - file object for the log file.
    '''
    print '\n', SEP, '\n'
    print 'Processing', pkg

    try:
        out = subprocess.check_output(['sudo', 'rpm', '-q', '-l', pkg],
                                      stderr=pkg_log)

    except subprocess.CalledProcessError as e:
        pkg_log.write(
            '\'sudo rpm -q -l %s\' returned %d.\n' % (pkg, e.returncode))
        pkg_log.write('Failed to check %s\n' % pkg)
        add_to_list(pkg, RES_FAILED_TO_CHECK)
        return False

    nfiles = 0
    failed = False

    for fl in out.split('\n'):
        if re_service.match(fl):
            # Got a .service file, check it.
            nfiles = nfiles + 1
            if not do_check(os.path.basename(fl), pkg_log):
                failed = True

    if nfiles == 0:
        add_to_list(pkg, RES_SKIPPED)
        ret = True
    elif failed:
        add_to_list(pkg, RES_FAILED)
        ret = False
    else:
        add_to_list(pkg, RES_SUCCEEDED)
        ret = True

    pkg_log.write('\nNumber of .service files checked: %d.\n' % nfiles)
    return ret


def check_packages(available_file, installed):
    '''Check the packages listed in 'available_file'.

    'available_file' - the file with the list of available packages.
    'installed' - the collection of the names of installed packages.
    '''
    to_check = set()
    with open(available_file, 'r') as f:
        for line in f:
            to_check.add(line.rstrip())

    print 'Number of packages to check:', len(to_check)

    vmem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    vmem_used_start = vmem.total - vmem.available
    swap_used_start = swap.used

    print 'Memory: total = %s, used = %s' % (
        mem_to_str(vmem.total),
        mem_to_str(vmem_used_start))

    print 'Swap: total = %s, used = %s' % (
        mem_to_str(swap.total),
        mem_to_str(swap_used_start))

    passed = 0

    for pkg in to_check:
        #print 40 * '=', '\n'

        pkg_log_path = os.path.join(RESULT_DIR, 'pkg_' + pkg + '.log')
        if os.path.exists(pkg_log_path):
            os.remove(pkg_log_path)

        with open(pkg_log_path, 'w') as pkg_log:

            to_install = False
            if not pkg in installed:
                pkg_log.write('Installing ' + pkg + '\n')
                pkg_log.flush()
                to_install = True

                try:
                    subprocess.check_call(
                        ['sudo', 'yum', 'install', '-y', pkg],
                        stdout=pkg_log, stderr=pkg_log)

                except subprocess.CalledProcessError as e:
                    pkg_log.write('Failed to install ' + pkg + '\n')
                    pkg_log.write('yum returned %d\n' % e.returncode)
                    add_to_list(pkg, RES_FAILED_TO_INSTALL)
                    continue
            else:
                pkg_log.write('Already installed: ' + pkg + '\n')

            if check_services(pkg, pkg_log):
                passed = passed + 1

            if to_install:
                try:
                    pkg_log.write('\nRemoving ' + pkg + '\n')
                    subprocess.check_call(
                        ['sudo', 'yum', 'remove', '-y', pkg],
                        stdout=pkg_log, stderr=pkg_log)

                except subprocess.CalledProcessError as e:
                    pkg_log.write('Failed to remove ' + pkg + '\n')
                    pkg_log.write('yum remove returned %d.\n' % e.returncode)
                    add_to_list(pkg, RES_FAILED_TO_REMOVE)
                    continue

            vmem_used_prev = vmem.total - vmem.available
            swap_used_prev = swap.used

            vmem = psutil.virtual_memory()
            swap = psutil.swap_memory()

            vmem_used = vmem.total - vmem.available

            print 'Memory: total = %s, used = %s (%s)' % (
                mem_to_str(vmem.total),
                mem_to_str(vmem_used),
                mem_to_str(vmem_used - vmem_used_prev, delta=True))

            print 'Swap: total = %s, used = %s (%s)' % (
                mem_to_str(swap.total),
                mem_to_str(swap.used),
                mem_to_str(swap.used - swap_used_prev, delta=True))

    mem_log_path = os.path.join(RESULT_DIR, 'memory_summary.log')
    with open(mem_log_path, 'w') as mem_log:
        vmem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        vmem_used = vmem.total - vmem.available

        mem_log.write('Memory usage delta: %s\nSwap usage delta: %s\n' % (
            mem_to_str(vmem_used - vmem_used_start, delta=True),
            mem_to_str(swap.used - swap_used_start, delta=True)))

    print SEP
    print 'Tests passed for %d of %d package(s)' % (passed, len(to_check))
    print SEP


def get_status(service, pkg_log):
    '''Returns the status of the given service as a lowercase string.

    'service' - name of the service without the path.
    Return value: 'active', 'inactive', 'failed', ..., None if failed to
    determine the status.
    '''
    try:
        out = subprocess.check_output(['sudo', 'systemctl', 'show',
                                       '--property=ActiveState', service],
                                      stderr=pkg_log)
        prop, value = out.strip().split('=')
        if prop != 'ActiveState' or not value:
            pkg_log.write(
            'Failed to obtain status of %s, the response was \"%s\"\n' % (
                service, out.strip()))
            return None

        return value.lower()

    except subprocess.CalledProcessError as e:
        pkg_log.write(
            'Failed to obtain status of %s (systemctl returned %d).\n' % (
                service, e.returncode))
        return None


def do_check(service, pkg_log):
    '''Check the given service if it is not already active.

    If the service is not already active, try to activate it and check the
    status.

    Returns False on failure, True otherwise.
    '''
    pkg_log.write(SEP + '\n\n')
    pkg_log.write('Checking %s.\n' % service)

    status = get_status(service, pkg_log)
    if status == STATUS_ACTIVE:
        # The service is already running, assuming it is working OK.
        return True
    elif status == STATUS_FAILED:
        # The system tried to start the service before but failed.
        pkg_log.write('Service \"%s\" failed to start at boot.\n' % service)
        pkg_log.flush()
        subprocess.call(['sudo', 'systemctl', 'status', service],
                        stdout=pkg_log)
        return False
    elif status != STATUS_INACTIVE:
        pkg_log.write('Unknown status: %s.\n' % status)
        return False

    # The service is available but has not started yet (or the corresponding
    # process has already exited), try to start it.
    ret = subprocess.call(['sudo', 'systemctl', 'start', service],
                          stdout=pkg_log)
    if ret != 0:
        pkg_log.write('Failed to start service \"%s\".\n' % service)
        pkg_log.write('Status:\n')
        pkg_log.flush()
        subprocess.call(['sudo', 'systemctl', 'status', service],
                        stdout=pkg_log)
        return False

    status = get_status(service, pkg_log)
    success = True
    if status != STATUS_ACTIVE and status != STATUS_INACTIVE:
        pkg_log.write('Failed to start service \"%s\". Status: \"%s\"\n' % (
            service, status))
        pkg_log.flush()
        subprocess.call(['sudo', 'systemctl', 'status', service],
                        stdout=pkg_log)
        success = False

    # Stop the service
    ret = subprocess.call(['sudo', 'systemctl', 'stop', service],
                          stdout=pkg_log)
    if ret != 0:
        pkg_log.write('Failed to stop service \"%s\".\n' % service)
        return False

    return success


# main
if __name__ == '__main__':
    if len(sys.argv) != 2:
        print 'Usage: '
        print '\t' + sys.argv[0] + ' <packages_list_file>'
        sys.exit(1)

    my_out = SyncedOut(sys.stdout)
    sys.stdout = my_out

    print 'Started at', datetime.today()

    fnames = [RES_FAILED_TO_INSTALL, RES_FAILED_TO_REMOVE,
              RES_FAILED_TO_CHECK, RES_FAILED, RES_SUCCEEDED, RES_SKIPPED]
    for fname in fnames:
        if os.path.exists(fname):
            os.remove(fname)

    installed = get_installed_list()
    print 'Installed:', len(installed)

    available_file = sys.argv[1]
    print 'Processing the packages listed in \'%s\'' % available_file
    check_packages(available_file, installed)

    journal = os.path.join(RESULT_DIR, 'journalctl_ab.log')
    with open(journal, 'w') as jrnl:
        subprocess.call(['sudo', 'journalctl', '-ab'], stdout=jrnl)

    print 'Completed at', datetime.today()
