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
"""
Developer's note:
This script starts the modules as processes for multithreading purposes.
Multithreading in python is broken, so separated processes are necessary. Don't
try to revert to threads. But spawning a new process is made by clonning the
current one. That means that all variables a stuff will be copied (kinda).
Also, when a process spawns another, they all are part of the same process
groupid. When you press CTRL+C, the signal is sent to all processes in the same
groupid. To be able to cleanly exit, child processes need to know their role
and react accordingly to the signal. I do that by making the entry point of
every child process a function in this script (main(pipe, pkg)) that will
flag the process correctly, clean up resources and start the correct run loop.
The lifetime thus becomes:
 - This script starts
 - This script spawns a process
 -- Child process runs `main()` function
 -- Child's `processes` is cleared and `process_type` set to 'child'
 -- Child process enters package main loop
 - User hits CTRL+C, both process receives SIGINT
 -- Child process ignores SIGINT
 - Parent process handles it and sends 'quit' to all children through pipes
 -- Child process receives 'quit' command, cleans up and exits gracefully
 - Parent process waits for all children to terminate and then exits
"""

import hashlib
import os
import signal
import sys
import time
from multiprocessing import Pipe, Process

from moirai import __version__
from moirai import decorators
from moirai.database import DatabaseV1
from moirai.installer import install

PROCESSES = {}
PS = ['webapi', 'hardware']
PROCESS_TYPE = 'main'
WEBSOCKET = None

sys.path.append(os.path.join(os.path.splitdrive(sys.executable)[0], 'opt'))


def signal_handler(*_):
    """
    Handles system signals, reacting and sending messages to spawned processes
    """
    global PS
    # Only respond to SIGINT if we're on parent process.
    # Child processes will be asked to quit.
    if PROCESS_TYPE == 'main':
        print('')
        # Ask each child process to quit
        for key in reversed(PS):
            process, pipe = PROCESSES[key]
            pipe.send(('quit', None))
            process.join()
        print('Shutting down Moirai...')
        sys.exit(0)


def spawn_process(name):
    """
    Spawns a new processes for module named `name`
    """
    pipe_main, pipe_process = Pipe()
    process = Process(target=main, args=(pipe_process, name))
    PROCESSES[name] = (process, pipe_main)
    process.start()


def init(name):
    """
    Send the INIT command to the process named `name`
    """
    global PROCESSES
    pipe = PROCESSES[name][1]
    pipe.send(('init', None))


def main(pipe, name):
    """
    This is the main function of child processes. It will flag this process
    as child and start the event loop in the correct package. Setting
    processes to None is only to keep this instance clean, as it doesn't need
    to know about the existence of other processes.
    """
    global PROCESSES, PROCESS_TYPE
    PROCESSES = None
    PROCESS_TYPE = 'child'
    if name == 'hardware':
        import moirai.hardware as pkg
    elif name == 'webapi':
        import moirai.webapi as pkg
    pkg.main(pipe)


def query_alive(name):
    """
    Checks if process `name` is answering, e.q. if it's not stale
    """
    global PROCESSES
    pipe = PROCESSES[name][1]
    if pipe.poll():
        pipe.recv()
    pipe.send(('alive', None))
    cmd, __ = pipe.recv()
    return cmd == 'alive'


def start():
    """
    Entry point of the application
    """
    global PROCESSES, PS

    if '--version' in sys.argv:
        print(__version__)
        return

    if '--help' in sys.argv:
        print(fr'Moirai version {__version__}')
        print(r'Options:')
        print('\t--version Prints version')
        print('\t--install Tries to install dependencies.')
        print(
            '\t--sudo Uses sudo to install packages. You still need write access to /opt.'
        )
        print('\t--set-password=pwd Sets the password to pwd')
        print('')
        print('\tThe installer does not behave well with PyENV')
        return

    if '--install' in sys.argv:
        install('--sudo' in sys.argv)
        return

    # Catches SIGINT (CTRL+C)
    signal.signal(signal.SIGINT, signal_handler)
    print('Starting Moirai...')
    print('To quit press CTRL+C (^C on Macs)')
    print('Logging to %s' % decorators.log_file_path())

    # Creates a processs for each module of moirai
    for process in PS:
        spawn_process(process)

    time.sleep(1)

    while not all([query_alive(p) for p in PROCESSES]):
        pass

    # parses command line arguments
    has_cmd = False
    for arg in sys.argv:
        if arg.startswith('--set-password='):
            pswd = arg.split('=')[-1]
            if not pswd:
                pswd = None
            else:
                hasher = hashlib.sha512()
                hasher.update(bytes(pswd, 'utf-8'))
                pswd = hasher.hexdigest()
            print("Setting password to %s" % pswd)
            has_cmd = True
            database = DatabaseV1()
            database.set_setting('password', pswd)
    if has_cmd:
        signal_handler(None, None)
    else:
        for process in PS:
            init(process)
        time.sleep(1)
    last_message = time.time() + 60

    while True:
        if time.time() - last_message > 1:
            time.sleep(1)
        for name in PS:
            pipe = PROCESSES[name][1]
            if pipe.poll():
                last_message = time.time()
                command, args = pipe.recv()
                if command == 'quit':
                    signal_handler(None, None)
                elif command == 'connect':
                    pkg_from, pkg_to = args
                    pipe_to = PROCESSES[pkg_to][1]
                    process1, process2 = Pipe()
                    pipe_to.send(('connect', (pkg_from, process1)))
                    status, __ = pipe_to.recv()
                    if status == 'ok':
                        pipe.send(('ok', process2))
                    else:
                        pipe.send(('error', None))
