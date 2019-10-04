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

import subprocess
import sys

from os import listdir, makedirs
from os.path import expanduser, isdir, isfile, join, normpath
from shutil import move, copy2

PYTHON_EXE = normpath(sys.executable)

MBED_REPOSITORY = "https://github.com/ARMmbed/mbed-os.git"
MBED_VERSION = "latest"

PIO_PACKAGES_ROOT = join(expanduser("~"), ".platformio", "packages")
PIO_MBED_PACKAGE_ROOT = join(PIO_PACKAGES_ROOT, "framework-mbed")
LATEST_MBED_PACKAGE_ROOT = join(PIO_PACKAGES_ROOT, "framework-mbed-latest")


def exec_cmd(*args, **kwargs):
    print(" ".join(args[0]))
    return subprocess.call(*args, **kwargs)


def clone_latest_mbed_release():
    print ("Cloning the latest framework release ...")
    exec_cmd([
        "git", "clone", MBED_REPOSITORY,
        "--branch", MBED_VERSION, LATEST_MBED_PACKAGE_ROOT
    ])

    assert isdir(LATEST_MBED_PACKAGE_ROOT)


def move_package_file():
    print ("Moving package.json ...")
    move(
        join(PIO_MBED_PACKAGE_ROOT, "package.json"),
        join(LATEST_MBED_PACKAGE_ROOT, "package.json")
    )

    assert isfile(join(LATEST_MBED_PACKAGE_ROOT, "package.json"))


def copy_pio_tools():
    tools_path = join(LATEST_MBED_PACKAGE_ROOT, "platformio")
    print ("Copying files to %s" % tools_path)
    if not isdir(tools_path):
        makedirs(tools_path)
    for f in listdir("."):
        if isfile(f):
            copy2(f, tools_path)

    assert isfile(join(tools_path, "platformio-build.py"))


def build_deps():
    print ("Building package dependencies ...")
    exec_cmd([
        PYTHON_EXE, join(
            LATEST_MBED_PACKAGE_ROOT, "platformio", "install_python_deps.py")
    ])

    assert isdir(join(LATEST_MBED_PACKAGE_ROOT, "platformio", "package_deps"))


def switch_to_latest_framework():
    clone_latest_mbed_release()
    move_package_file()
    copy_pio_tools()
    build_deps()


switch_to_latest_framework()
