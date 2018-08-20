#!/usr/bin/env python3
# -*- coding: utf-8; -*-
#
# Copyright (c) 2016 Álan Crístoffer
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import glob
import os
import platform
import re
import shutil
import sys
import zipfile

from urllib.request import urlopen
from pathlib import Path

opt = os.path.join(os.path.abspath(os.sep), 'opt')


def pi_version():
    """Detect the version of the Raspberry Pi.  Returns either 1, 2 or
    None depending on if it's a Raspberry Pi 1 (model A, B, A+, B+),
    Raspberry Pi 2 (model B+), or not a Raspberry Pi.
    https://github.com/adafruit/Adafruit_Python_GPIO/blob/master/Adafruit_GPIO/Platform.py
    """
    if not os.path.isfile('/proc/cpuinfo'):
        return None
    # Check /proc/cpuinfo for the Hardware field value.
    # 2708 is pi 1
    # 2709 is pi 2
    # Anything else is not a pi.
    with open('/proc/cpuinfo', 'r') as infile:
        cpuinfo = infile.read()
    # Match a line like 'Hardware   : BCM2709'
    match = re.search(
        '^Hardware\s+:\s+(\w+)$', cpuinfo, flags=re.MULTILINE | re.IGNORECASE)
    if not match:
        # Couldn't find the hardware, assume it isn't a pi.
        return None
    if match.group(1) == 'BCM2708':
        # Pi 1
        return 1
    elif match.group(1) == 'BCM2709':
        # Pi 2
        return 2
    elif match.group(1) == 'BCM2835':
        # Pi 3
        return 3
    else:
        # Something else, not a pi.
        return None


class cd:
    """Context manager for changing the current working directory"""

    def __init__(self, newPath):
        self.newPath = os.path.expanduser(newPath)

    def __enter__(self):
        self.savedPath = os.getcwd()
        os.chdir(self.newPath)

    def __exit__(self, etype, value, traceback):
        os.chdir(self.savedPath)


def download_mysql_connector(use_sudo):
    sudo = 'sudo' if use_sudo else ''
    print('Downloading MySQL Connector/Python')
    try:
        url = 'https://dev.mysql.com/get/Downloads/Connector-Python/mysql-connector-python-2.1.7.tar.gz'
        contents = urlopen(url).read()
        with open('mysql.txz', 'wb') as f:
            f.write(contents)
        os.system('tar xf mysql.txz')
        with cd('mysql-connector-python-2.1.7'):
            os.system('%s %s setup.py install' % (sudo, sys.executable))
        return True
    except:
        return False


def download_snap7_linux(use_sudo):
    sudo = 'sudo' if use_sudo else ''
    arch = {
        'x64': 'x86_64',
        'ia32': 'i386',
        'x86': 'i386',
        'armv7': 'arm_v7',
        'armv6': 'arm_v6'
    }.get(platform.machine(), platform.machine())
    print('Downloading snap7...')
    try:
        if not os.path.exists('snap7.zip'):
            snap7url = 'https://sourceforge.net/projects/snap7/files/1.4.2/snap7-full-1.4.2.7z/download'
            contents = urlopen(snap7url).read()
            with open('snap7.zip', 'wb') as f:
                f.write(contents)
        os.system('7z x -y snap7.zip')
        with cd('snap7-full-1.4.2/build/unix'):
            os.system(f'make -f {arch}_linux.mk')
        lib = f'snap7-full-1.4.2/build/bin/{arch}-linux/libsnap7.so'
        shutil.copy(lib, os.path.join(opt, 'libsnap7.so'))
        os.chmod(os.path.join(opt, 'libsnap7.so'), 0o777)
        os.system(f'{sudo} ldconfig /opt')
        os.remove('snap7.zip')
        shutil.rmtree('snap7-full-1.4.2')
        return True
    except:
        return False


def download_snap7_win():
    print('Downloading snap7...')
    try:
        snap7url = 'https://sourceforge.net/projects/snap7/files/latest/download?source=files'
        contents = urlopen(snap7url).read()
        with open('snap7.zip', 'wb') as f:
            f.write(contents)
        with zipfile.ZipFile('snap7.zip', 'r') as zip_ref:
            zip_ref.extractall('snap7')
        dll = list(glob.iglob('snap7/**/*.dll'))[0]
        shutil.copy(dll, os.path.join(opt, 'snap7.dll'))
        os.remove('snap7.zip')
        shutil.rmtree('snap7')
        return True
    except:
        return False


def install(use_sudo=False):
    try:
        osname = platform.system()
        if osname == 'Windows':
            print('You need to install MongoDB.')
            print('https://www.mongodb.com')
            print('')
        elif osname == 'Darwin':
            print('Platform: macOS')
            brew = os.popen('which brew').read()
            if len(brew) > 0:
                print('Using Homebrew to install dependencies.')
                print('Will now execute: [brew install mongodb snap7]')
                result = os.system('brew install mongodb snap7')
                if result == 0:
                    print('Installation finished.')
                else:
                    print('Something went wrong. Try installing manually:')
                    print('brew install mongodb snap7')
            else:
                print('Homebrew not installed, cannot continue alone.')
                print('You need to install MongoDB and snap7.')
                print('https://www.mongodb.com')
                print('https://sourceforge.net/projects/snap7/files')
        elif osname == 'Linux':
            success = False
            sudo = 'sudo ' if use_sudo else ''
            if pi_version() is not None:
                print('Platform: Raspberry Pi')
                cmd = sudo + 'DEBIAN_FRONTEND=noninteractive apt-get install -y mysql-server build-essential p7zip-full'
                print('Using APT to install dependencies.')
                print(f'Will now execute: [{cmd}]')
                result = os.system(cmd)
                with open('%s/.moirai.json' % str(Path.home()), 'a+') as f:
                    c = f.read()
                    if not c:
                        f.write('{"database":{"adapter":"mysql"}}')
                if result == 0:
                    mysql = download_mysql_connector(use_sudo)
                    snap7 = download_snap7_linux(use_sudo)
                    if mysql and snap7:
                        print('Installation finished.')
                    else:
                        print('Something went wrong. Try installing manually:')
                        print('https://sourceforge.net/projects/snap7/files')
                else:
                    print('Something went wrong. Try installing manually:')
                    print(cmd)
                    print('After that, you need to install snap7.')
                    print('https://sourceforge.net/projects/snap7/files')
            elif len(os.popen('which zypper').read()) > 0:
                print('Platform: OpenSuse')
                cmd1 = sudo + 'zypper -n in -t pattern devel_basis'
                cmd2 = sudo + 'zypper -n in mongodb p7zip'
                print('Using Zypper to install dependencies.')
                print(f'Will now execute: [{cmd1}]')
                result1 = os.system(cmd1)
                print(f'Will now execute: [{cmd2}]')
                result2 = os.system(cmd2)
                if result1 == 0 and result2 == 0:
                    if download_snap7_linux(use_sudo):
                        print('Installation finished.')
                    else:
                        print('Something went wrong. Try installing manually:')
                        print('https://sourceforge.net/projects/snap7/files')
                else:
                    print('Something went wrong. Try installing manually:')
                    print(cmd1)
                    print(cmd2)
                    print('After that, you need to install snap7.')
                    print('https://sourceforge.net/projects/snap7/files')
            elif len(os.popen('which apt-get').read()) > 0:
                print('Platform: Debian')
                cmd = sudo + 'apt-get install -y mongodb-server build-essential p7zip-full'
                print('Using APT to install dependencies.')
                print(f'Will now execute: [{cmd}]')
                result = os.system(cmd)
                if result == 0:
                    if download_snap7_linux(use_sudo):
                        print('Installation finished.')
                    else:
                        print('Something went wrong. Try installing manually:')
                        print('https://sourceforge.net/projects/snap7/files')
                else:
                    print('Something went wrong. Try installing manually:')
                    print(cmd)
                    print('After that, you need to install snap7.')
                    print('https://sourceforge.net/projects/snap7/files')
            elif len(os.popen('which dnf').read()) > 0:
                print('Platform: Fedora')
                cmd = sudo + 'dnf install -y @development-tools p7zip mongodb-server'
                print('Using DNF to install dependencies.')
                print(f'Will now execute: [{cmd}]')
                result = os.system(cmd)
                if result == 0:
                    if download_snap7_linux(use_sudo):
                        print('Installation finished.')
                    else:
                        print('Something went wrong. Try installing manually:')
                        print('https://sourceforge.net/projects/snap7/files')
                else:
                    print('Something went wrong. Try installing manually:')
                    print(cmd)
                    print('After that, you need to install snap7.')
                    print('https://sourceforge.net/projects/snap7/files')
            elif len(os.popen('which yum').read()) > 0:
                print('Platform: Fedora')
                cmd1 = sudo + 'yum groupinstall -y "Development Tools" "Development Libraries"'
                cmd2 = sudo + 'yum install -y p7zip mongodb-server'
                print('Using YUM to install dependencies.')
                print(f'Will now execute: [{cmd1}]')
                result1 = os.system(cmd1)
                print(f'Will now execute: [{cmd2}]')
                result2 = os.system(cmd2)
                if result1 == 0 and result2 == 0:
                    if download_snap7_linux(use_sudo):
                        print('Installation finished.')
                    else:
                        print('Something went wrong. Try installing manually:')
                        print('https://sourceforge.net/projects/snap7/files')
                else:
                    print('Something went wrong. Try installing manually:')
                    print(cmd1)
                    print(cmd2)
                    print('After that, you need to install snap7.')
                    print('https://sourceforge.net/projects/snap7/files')
            else:
                print('You need to install MongoDB and snap7.')
                print('https://www.mongodb.com')
                print('https://sourceforge.net/projects/snap7/files')
        elif osname == 'Windows':
            print('Trying to install MongoDB and snap7...')
            if download_snap7_win():
                print('Downloading MongoDB...')
                mongo = 'https://fastdl.mongodb.org/win32/mongodb-win32-x86_64-2008plus-ssl-4.0.1-signed.msi'
                contents = urlopen(mongo).read()
                with open('mongo.msi', 'wb') as f:
                    f.write(contents)
                result = os.system(
                    r'msiexec.exe /q /i mongo.msi INSTALLLOCATION="C:\Program Files\MongoDB\Server\4.0.1\" ADDLOCAL="all"'
                )
                if result:
                    print('Installation finished.')
                else:
                    print('You need to install MongoDB.')
                    print('https://www.mongodb.com')
            else:
                print('You need to install MongoDB and snap7.')
                print('https://www.mongodb.com')
                print('https://sourceforge.net/projects/snap7/files')
        else:
            print('You need to install MongoDB and snap7.')
            print('https://www.mongodb.com')
            print('https://sourceforge.net/projects/snap7/files')
    except:
        print('Something went wrong. Try installing manually.')
        print(
            'You need to install MongoDB (or MySQL for Raspberry 32bits) and snap7.'
        )
        print('https://www.mongodb.com')
        print('https://sourceforge.net/projects/snap7/files')
