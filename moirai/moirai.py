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
 - Parent process handles it and sends 'quit' to all child through pipes
 -- Child process receives 'quit' command, cleans up and exits gracefully
 - Parent process waits for all children to terminate and then exits
"""

from multiprocessing import Process, Pipe

import hashlib
import os
import signal
import sys
import time

processes = {}
process_type = 'main'
websocket = None


def signal_handler(signal, frame):
    # Only respond to SIGINT if we're on parent process.
    # Child processes will be asked to quit.
    if process_type == 'main':
        print('')
        # Ask each child process to quit
        for key in processes:
            process, pipe = processes[key]
            if key == 'websocket':
                process.terminate()
            else:
                pipe.send(('quit', None))
                process.join()
        print('Shutting down Moirai...')
        sys.exit(0)


def spawn_process(name):
    as_daemon = name != 'websocket'
    pipe_main, pipe_process = Pipe()
    p = Process(target=main, args=(pipe_process, name), daemon=as_daemon)
    processes[name] = (p, pipe_main)
    p.start()


def init(name):
    global processes
    pipe = processes[name][1]
    pipe.send(('init', None))


def main(pipe, name):
    # This is the main function of child processes. It will flag this process
    # as child and start the event loop in the correct package. Setting
    # processes to None is only to keep this instance clean, as it doesn't need
    # to know about the existence of other processes.
    global processes, process_type
    processes = None
    process_type = 'child'
    if name == 'database':
        import moirai.database as pkg
    elif name == 'io_manager':
        import moirai.io_manager as pkg
    elif name == 'tcp':
        import moirai.tcp as pkg
    elif name == 'websocket':
        import moirai.websocket as pkg
    pkg.main(pipe)


def start():
    global processes

    # Catches SIGINT (CTRL+C)
    signal.signal(signal.SIGINT, signal_handler)
    print('Starting Moirai...')
    print('To quit press CTRL+C (^C on Macs)')

    # Creates a processs for each module of moirai
    spawn_process('database')
    spawn_process('io_manager')
    spawn_process('tcp')
    spawn_process('websocket')

    while not all([processes[p][0].is_alive() for p in processes]):
        pass

    # parses command line arguments
    has_cmd = False
    for arg in sys.argv:
        if arg.startswith('--set-password='):
            pswd = arg.split('=')[-1]
            if len(pswd) == 0:
                pswd = None
            else:
                h = hashlib.sha512()
                h.update(bytes(pswd, 'utf-8'))
                pswd = h.hexdigest()
            print("Setting password to %s" % pswd)
            has_cmd = True
            processes['database'][1].send(('settings_set', ('password', pswd)))
    if has_cmd:
        signal_handler(None, None)
    else:
        init('database')
        init('io_manager')
        init('tcp')
        init('websocket')
    last_message = time.time() + 60

    while True:
        if time.time() - last_message > 1:
            time.sleep(1)
        for name, (_, pipe) in processes.items():
            if pipe.poll():
                last_message = time.time()
                command, args = pipe.recv()
                if command == 'quit':
                    signal_handler(None, None)
                elif command == 'connect':
                    pkg_from, pkg_to = args
                    pipe_to = processes[pkg_to][1]
                    p1, p2 = Pipe()
                    pipe_to.send(('connect', (pkg_from, p1)))
                    status, __ = pipe_to.recv()
                    if status == 'ok':
                        pipe.send(('ok', p2))
                    else:
                        pipe.send(('error', None))
