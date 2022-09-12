# Copyright 2019-present PlatformIO <contact@platformio.org>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import sys
import subprocess

from os import makedirs, remove, walk
from os.path import abspath, dirname, isdir, join, normpath
from shutil import rmtree

pio_tools = dirname(abspath(__file__))
python_exe = normpath(sys.executable)


def exec_cmd(*args, **kwargs):
    print(" ".join(args[0]))
    return subprocess.call(*args, **kwargs)


def build_packages():

    packages = (
        "intelhex==2.3.0",
        "jinja2==3.1.2",
        "pyelftools==0.25",
        "beautifulsoup4==4.11.1",
        "future==0.18.1",
        "prettytable==3.3.0",
        "jsonschema==4.14.0",
        "six==1.16.0"
    )

    target_dir = join(
        pio_tools,
        "package_deps",
        "py%d%s"
        % (
            sys.version_info.major,
            "_old" if sys.version_info < (3, 9) else "",
        ),
    )
    if isdir(target_dir):
        rmtree(target_dir)
    makedirs(target_dir)
    for name in packages:
        exec_cmd([
            python_exe, "-m", "pip", "install", "--no-cache-dir",
            "--no-compile", "-t", target_dir, name
        ])
    cleanup_packages(target_dir)


def cleanup_packages(package_dir):
    for root, dirs, files in walk(package_dir):
        for t in ("_test", "test", "tests"):
            if t in dirs:
                rmtree(join(root, t))
        for name in files:
            if name.endswith((".chm", ".pyc")):
                remove(join(root, name))

build_packages()
