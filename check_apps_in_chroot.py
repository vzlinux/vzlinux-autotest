#!/usr/bin/env python

# The script finds .desktop files for the applications in the given packages
# and attempts to launch these applications and check if they crash on
# startup.
#
# The script is based on check_apps_in_vm.py from rosa-autotest
# (https://abf.io/spectre/rosa-autotest) but intended to be run inside
# chroot and doesn't use cgroups.
#
# Usage:
#       python check_apps_in_vm.py <packages_list_file>
#
# <packages_list_file> file should contain names of the packages (without
# versions, etc.) from the repository to be processed.
# For simplicity, all currently enabled repositories will be used when
# installing the packages.
#
# The results will be available in the appropriate files in 'results'
# subdirectory of the current directory, see RES_* below.
# Each '*.list' file contains the list of packages of the particular kind.
# The main report will be in results/report.yaml file.

import os.path
import os
import subprocess
import re
import sys
import time
import resource
import signal
import shutil
import psutil
import string

from datetime import datetime
from ConfigParser import RawConfigParser
from ConfigParser import Error as ConfigParserError
from glob import glob


# Regexp for the needed paths to the .desktop files.
re_desktop = re.compile('/usr/share/(applications|autostart|kde4/services)/.*\\.desktop')

SEP = 72 * '='

# The section in a .desktop file we need.
SECTION = 'Desktop Entry'

# How long (in seconds) to wait after starting the application before
# killing it.
DEFAULT_TIMEOUT = 30

# How long (in seconds) to wait for the application to exit.
EXIT_TIMEOUT = 10

# The directory with the results
RESULT_DIR = '/tmp/results'

# Files with package lists of the given kind.
RES_FAILED_TO_INSTALL = RESULT_DIR + '/failed-to-install.list'
RES_FAILED_TO_REMOVE = RESULT_DIR + '/failed-to-remove.list'
RES_FAILED_TO_CHECK = RESULT_DIR + '/failed-to-check.list'
RES_CRASHED = RESULT_DIR + '/crashed.list'
RES_SUCCEEDED = RESULT_DIR + '/succeeded.list'
RES_SKIPPED = RESULT_DIR + '/skipped.list'

# Cgroup with subsystems
CGROUP = 'cpu,cpuacct:autotest'
# The file with the pids of the running processes that belong to the cgroup.
TASKS_FILE = '/cgroup/testing/autotest/tasks'

# Regexps to match when checking the output for exception information.
regexps_exception = [
    # Python
    re.compile('^Traceback \\(most recent call last\\):'),
    # Java
    re.compile('^Exception in thread'),
    # Perl
    re.compile('^Can\'t .* at line'),
    # binaries
    re.compile('^Could\'t load .*'),
    re.compile('.* cannot open shared object file'),
    re.compile('.* command not found')
    # TODO: add more
]


class Error(Exception):
    '''The custom error.'''
    pass


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
    out = subprocess.Popen(
        ['sudo', 'rpm', '-q', '-a', '--queryformat', '%{NAME}\n'],
        stdout=subprocess.PIPE).communicate()[0]
    return set(out.split('\n'))


def check_apps(pkg, pkg_log):
    '''Check the apps from the given package via their .desktop files.

    Returns True if all the apps have been checked successfully or the
    package contains no appropriate .desktop files and is therefore skipped.
    False is returned otherwise.

    'pkg' - name of the package.
    'pkg_log' - file object for the log file.
    '''
    print '\n', SEP, '\n'
    print 'Processing', pkg

    try:
        out = subprocess.Popen(['sudo', 'rpm', '-q', '-l', pkg],
                                      stdout=subprocess.PIPE,
                                      stderr=pkg_log).communicate()[0]

    except subprocess.CalledProcessError as e:
        pkg_log.write(
            '\'sudo rpm -q -l %s\' returned %d.\n' % (pkg, e.returncode))
        pkg_log.write('Failed to check %s\n' % pkg)
        add_to_list(pkg, RES_FAILED_TO_CHECK)
        return False

    cfg = RawConfigParser()

    nfiles = 0
    failed = False
    processed_commands = {}

    for fl in out.split('\n'):
        if re_desktop.match(fl):
            try:
                res = cfg.read(fl)
            except ConfigParserError as e:
                pkg_log.write('Error while parsing %s: %s.\n' % (fl, str(e)))
                continue

            if not res:
                pkg_log.write('File not found: %s.\n' % fl)
                continue

            if not cfg.has_section(SECTION):
                pkg_log.write(
                    'File %s does not have section \'%s\'.\n' % (fl, SECTION))
                continue

            if not cfg.has_option(SECTION, 'Type'):
                pkg_log.write(
                    'File %s does not have \'Type\' option.\n' % fl)
                continue

            tp = cfg.get(SECTION, 'Type')
            if tp != 'Application' and tp != 'Service':
                pkg_log.write(''.join([
                    'File ', fl,
                    ' does not specify and application (Type=', tp, ').\n']))
                continue

            if not cfg.has_option(SECTION, 'Exec'):
                pkg_log.write(
                    'File %s does not have \'Exec\' option.\n' % fl)
                continue

            exec_opt = cfg.get(SECTION, 'Exec')
            # Cut %-options, if any, as well as the rest of the command.
            ind = exec_opt.find('%')
            if ind != -1:
                exec_opt = exec_opt[ : ind]
                if exec_opt.endswith('\''):
                    exec_opt = exec_opt + 'Test\''

            command = exec_opt.strip()
            if command in processed_commands:
                pkg_log.write(
                    'Command \'%s\' has been already checked.\n' % command)
                continue
            processed_commands[command] = True

            if not cfg.has_option(SECTION, 'Name'):
                name = None
            else:
                name = cfg.get(SECTION, 'Name')

            # Got a .desktop file of the needed type with the needed
            # content, check it.
            nfiles = nfiles + 1
            if not do_check(pkg, name, command, pkg_log):
                failed = True

    if nfiles == 0:
        add_to_list(pkg, RES_SKIPPED)
        ret = True
    elif failed:
        add_to_list(pkg, RES_CRASHED)
        ret = False
    else:
        add_to_list(pkg, RES_SUCCEEDED)
        ret = True

    pkg_log.write('\nNumber of .desktop files checked: %d.\n' % nfiles)
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

    if not os.path.exists(RESULT_DIR):
        os.mkdir(RESULT_DIR)

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

            if check_apps(pkg, pkg_log):
                passed = passed + 1

            if to_install:
                try:
                    pkg_log.write('\nRemoving ' + pkg + '\n')
                    subprocess.check_call(
                        ['sudo', 'yum', 'remove', '-y', pkg],
                        stdout=pkg_log, stderr=pkg_log)
                    #subprocess.check_call(
                    #    ['sudo', 'urpme', '--auto', '--auto-orphans'],
                    #    stdout=pkg_log, stderr=pkg_log)

                except subprocess.CalledProcessError as e:
                    pkg_log.write('Failed to remove ' + pkg + '\n')
                    pkg_log.write('yum returned %d.\n' % e.returncode)
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


def kill_as_root(pid, sig, pkg_log):
    '''Send the signal to the process with the given PID as root.'''
    try:
        subprocess.check_call(
            ['sudo', 'kill', '-' + str(sig), str(pid)],
            stdout=pkg_log, stderr=pkg_log)

    except subprocess.CalledProcessError as e:
        pkg_log.write(''.join([
            'Failed to execute ',
            '\'kill -%d %d\', exit code: %d\n' % (sig, pid, e.returncode)]))
    except OSError, e:
        pkg_log.write(''.join([
            'Failed to execute ',
            '\'kill -%d %d\': %s\n' % (sig, pid, str(e))]))


def kill_group(sig, pkg_log, as_root=False):
    '''Send signal 'sig' to all running processes that belong to the cgroup.

    Returns True if there was at least one process there, False otherwise.

    If 'as_root' is True, the signal will be sent as root, otherwise - as
    the current user.
    '''
    ret = False

    with open(TASKS_FILE, 'r') as f:
        for line in f:
            pid_str = line.strip()
            pid = int(pid_str)
            if pid > 0:
                pkg_log.write(
                    'Sending signal %d to the process %d.\n' % (sig, pid))
                if as_root:
                    kill_as_root(pid, sig, pkg_log)
                else:
                    os.kill(pid, sig)
                ret = True

    return ret


def do_check(pkg, name, command, pkg_log, timeout=DEFAULT_TIMEOUT):
    '''Run the given application and see if it crashes.

    Returns False if the application crashed, True otherwise.
    '''
    pkg_log.write(SEP + '\n\n')
    if name:
        pkg_log.write('Checking %s.\n' % name)
    pkg_log.write('Command: \'%s\'\n\n' % command)

    # Remove all core.* files first
    files = glob('./core.*')
    for fl in files:
        os.remove(fl)

    crashed = False

    try:
        cmd = string.split(command, " ")
        proc = subprocess.Popen(
            ["xvfb-run"] + cmd, stdout=pkg_log, stderr=pkg_log)
#            ['cgexec', '-g', CGROUP, command], stdout=pkg_log,
#            stderr=pkg_log)
        time.sleep(timeout)
        proc.send_signal(signal.SIGTERM)
        time.sleep(EXIT_TIMEOUT)
        proc.send_signal(signal.SIGKILL)

        # Kill the process as well as any other processes it has spawned.
#        if kill_group(signal.SIGTERM, pkg_log):
#            time.sleep(EXIT_TIMEOUT)

        # Just to make sure they are killed
#        if kill_group(signal.SIGKILL, pkg_log):
#            time.sleep(EXIT_TIMEOUT)

        pkg_log.flush()
        crashed = crashed_procs(pkg, pkg_log)
	ldproc = subprocess.Popen('ldd' + ' ' '$(which '+ command + ')', shell=True, stdout=pkg_log, stderr=pkg_log)

        # Just in case (zombies, uninterruptible sleeps in a driver, ...)
        ret = proc.poll()
        if ret is None:
            pkg_log.write('Failed to kill the process.\n')
            #crashed = True

    except OSError, e:
        pkg_log.write('Failed to execute the command: %s\n' % str(e))
        #crashed = True

    # Just in case, to avoid stray processes.
#    kill_group(signal.SIGKILL, pkg_log, as_root=True)
    return not crashed


def enable_core_dumps():
    '''Enable generation of core dumps for this process and its children'''

    # Similar to 'ulimit -c unlimited'.
    resource.setrlimit(resource.RLIMIT_CORE, (-1, -1))

    # Make sure the core dumps are created as plain files and not passed to
    # systemd or whatever.
    # The files will be named 'core.<pid>'.
    subprocess.call(['sudo', 'sh', '-c',
                     'echo core > /proc/sys/kernel/core_pattern'])


def crashed_procs(pkg, pkg_log):
    '''Returns True if some processes have crashed, False otherwise.'''

    with open(pkg_log.name, 'r') as f:
        for line in f:
            for reg in regexps_exception:
                if reg.match(line.strip()):
                    return True

    files = glob('./core.*')
    if files:
        pkg_log.write('The processes with the following PIDs have crashed:\n')
        for fl in files:
            _, _, pid_str = fl.rpartition('.')
            pkg_log.write('\t' + pid_str + '\n')
            saved_dump = ''.join(
                [RESULT_DIR, '/dump_', pkg, '.', pid_str, '.core'])
            if not os.path.exists(saved_dump):
                shutil.move(fl, saved_dump)

        return True

    return False


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
              RES_FAILED_TO_CHECK, RES_CRASHED, RES_SUCCEEDED, RES_SKIPPED]
    for fname in fnames:
        if os.path.exists(fname):
            os.remove(fname)

#    enable_core_dumps()

    installed = get_installed_list()
    print 'Installed:', len(installed)

    available_file = sys.argv[1]
    print 'Processing the packages listed in \'%s\'' % available_file
    check_packages(available_file, installed)

    print 'Completed at', datetime.today()
