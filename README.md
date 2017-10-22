# moirai

Moirai is the backend for the platform. It is developed as part of my scientific
initiation project, named Plataformas de baixo custo para controle de processos
(low-cost platform for process control), developed at CEFET-MG (Brazil) under
the supervision of Prof. Dr. Valter Leite. The project was developed through a
FAPEMIG scholaship.

It's meant to be installed in a computer near the plant, so it can be
remote-controlled by [Lachesis](https://github.com/acristoffers/Lachesis). It
exposes a RESTful API that let's you configure the hardware, save tests and
controllers, execute them and fetch the results in real-time or after the
execution finishes.

Controllers for this platform are written in Python 3 and can use any librarie
available in the computer where _moirai_ is running. It already depends on NumPy
and SciPy, as they are commonly used. This platform manages the hardware
interfacing through the [ahio](https://github.com/acristoffers/ahio) libray, so
extending it's hardware capabilities is a question of extending AHIO, which
should be simple. Execution time, sampling time, input querying and output
updating is managed by the application and let's you focus on your
controller/model.

## Installation

Use pip to install. This is a Python 3 application and won't run in Python 2.
Use `pip install moirai` or `pip3 install moirai` to install it. It also has
other dependencies not installable through pip. Those can be installed by
running `moirai --install`. Namely, it will install MongoDB and the Snap7
library. It's designed to work on Windows, macOS (with Homebrew) and Linux
(apt-get, dnf, yum and zypper).

## License

Copyright (c) 2016 Álan Crístoffer

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
