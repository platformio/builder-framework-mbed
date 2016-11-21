# Copyright 2014-present PlatformIO <contact@platformio.org>
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

"""
mbed

The mbed framework The mbed SDK has been designed to provide enough
hardware abstraction to be intuitive and concise, yet powerful enough to
build complex projects. It is built on the low-level ARM CMSIS APIs,
allowing you to code down to the metal if needed. In addition to RTOS,
USB and Networking libraries, a cookbook of hundreds of reusable
peripheral and module libraries have been built on top of the SDK by
the mbed Developer Community.

http://mbed.org/
"""

import sys
from copy import copy
import xml.etree.ElementTree as ElementTree
from hashlib import md5
import json
from os import walk, listdir
from os.path import basename, isdir, isfile, join, relpath


from platformio.builder.tools.platformio import SRC_BUILD_EXT, SRC_HEADER_EXT
from platformio.builder.tools.piolib import PlatformIOLibBuilder

from SCons.Script import DefaultEnvironment

env = DefaultEnvironment()

FRAMEWORK_DIR = env.PioPlatform().get_package_dir("framework-mbed")
assert isdir(FRAMEWORK_DIR)

if isfile(join(FRAMEWORK_DIR, 'mbed.h')):
    # mbed >= 5.2
    TARGETS_DIRS = [
        join(FRAMEWORK_DIR, 'cmsis'),
        join(FRAMEWORK_DIR, 'hal'),
        join(FRAMEWORK_DIR, 'targets'),
        join(FRAMEWORK_DIR, 'platform'),
    ]
    TARGETS_FILE = join(FRAMEWORK_DIR, 'targets', 'targets.json')
    CPPPATH = [
        join(FRAMEWORK_DIR, "cmsis"),
        join(FRAMEWORK_DIR, "drivers"),
        join(FRAMEWORK_DIR, "hal"),
        join(FRAMEWORK_DIR, "hal", "storage_abstraction"),
        join(FRAMEWORK_DIR, "platform"),
        join(FRAMEWORK_DIR, "features"),
        join(FRAMEWORK_DIR),
    ]
    LIBS_DIRS = [
        join(FRAMEWORK_DIR, "rtos"),
        join(FRAMEWORK_DIR, "events"),
        join(FRAMEWORK_DIR, "features"),
    ]
    HAL_COMMON = (join("$BUILD_DIR", "FrameworkMbedDrivers"),
                  join(FRAMEWORK_DIR, "drivers"))
    CXXFLAGS = [
        '-DMBED_CONF_PLATFORM_DEFAULT_SERIAL_BAUD_RATE=115200',
    ]
    CFLAGS = [
        '-DMBED_CONF_PLATFORM_DEFAULT_SERIAL_BAUD_RATE=115200',
    ]
else:
    # mbed <5.2 (mbed lib 3.127)
    TARGETS_DIRS = [
        join(FRAMEWORK_DIR, 'hal', 'targets', 'cmsis'),
        join(FRAMEWORK_DIR, 'hal', 'targets', 'hal'),
    ]
    TARGETS_FILE = join(FRAMEWORK_DIR, 'hal', 'targets.json')
    CPPPATH = [
        join(FRAMEWORK_DIR, "hal", "api"),
        join(FRAMEWORK_DIR, "hal", "hal"),
        join(FRAMEWORK_DIR, "hal", "hal", "storage_abstraction"),
        join(FRAMEWORK_DIR, "hal", "common")
    ]
    LIBS_DIRS = [
        join(FRAMEWORK_DIR, "rtos"),
        join(FRAMEWORK_DIR, "libraries"),
        join(FRAMEWORK_DIR, "libraries", "net"),
        join(FRAMEWORK_DIR, "libraries", "rpc"),
        join(FRAMEWORK_DIR, "libraries", "dsp"),
        join(FRAMEWORK_DIR, "libraries", "USBHost"),
        join(FRAMEWORK_DIR, "libraries", "USBDevice"),
    ]
    HAL_COMMON = (join("$BUILD_DIR", "FrameworkMbedHalCommon"),
                  join(FRAMEWORK_DIR, "hal", "common"))
    CXXFLAGS = [
    ]
    CFLAGS = [
    ]


MBED_VARIANTS = {
    "blueboard_lpc11u24": "LPC11U24",
    "dipcortexm0": "LPC11U24",
    "seeedArchPro": "ARCH_PRO",
    "seeedArchBLE": "ARCH_BLE",
    "seeedTinyBLE": "SEEED_TINY_BLE",
    "seeedArchMax": "ARCH_MAX",
    "seeedArchGPRS": "ARCH_GPRS",
    "seeedArchLink": "ARCH_LINK",
    "ubloxc027": "UBLOX_C027",
    "lpc1114fn28": "LPC1114",
    "lpc11u35": "LPC11U35_401",
    "mbuino": "LPC11U24",
    "nrf51_mkit": "NRF51822",
    "redBearLab": "RBLAB_NRF51822",
    "redBearLabBLENano": "RBLAB_BLENANO",
    "frdm_kl25z": "KL25Z",
    "frdm_kl26z": "KL26Z",
    "frdm_kl27z": "KL27Z",
    "frdm_kl43z": "KL43Z",
    "frdm_kl46z": "KL46Z",
    "frdm_k64f": "K64F",
    "frdm_kl05z": "KL05Z",
    "frdm_k20d50m": "K20D50M",
    "frdm_k22f": "K22F",
    "teensy31": "TEENSY3_1",
    "dfcm_nnn40": "DELTA_DFCM_NNN40",
    "samr21_xpro": "SAMR21G18A",
    "saml21_xpro_b": "SAML21J18A",
    "samd21_xpro": "SAMD21J18A",
    "bbcmicrobit": "NRF51_MICROBIT",
    "bbcmicrobit_b": "NRF51_MICROBIT_B"
}


def parse_eix_file(filename):
    result = {}
    paths = (
        ("CFLAGS", "./Target/Source/CC/Switch"),
        ("CXXFLAGS", "./Target/Source/CPPC/Switch"),
        ("CPPDEFINES", "./Target/Source/Symbols/Symbol"),
        ("FILES", "./Target/Files/File"),
        ("LINKFLAGS", "./Target/Source/LD/Switch"),
        ("OBJFILES", "./Target/Source/Addobjects/Addobject"),
        ("LIBPATH", "./Target/Linker/Librarypaths/Librarypath"),
        ("STDLIBS", "./Target/Source/Syslibs/Library"),
        ("LDSCRIPT_PATH", "./Target/Source/Scriptfile"),
        ("CPPPATH", "./Target/Compiler/Includepaths/Includepath")
    )

    tree = ElementTree.parse(filename)

    for (key, path) in paths:
        if key not in result:
            result[key] = []

        for node in tree.findall(path):
            _nkeys = node.keys()
            if node.get("name") in ("-include", "mbed_config.h"):
                continue
            result[key].append(
                node.get(_nkeys[0]) if len(_nkeys) == 1 else node.attrib)

    if "LINKFLAGS" in result:
        if "-c" in result["LINKFLAGS"]:
            result["LINKFLAGS"].remove("-c")
        for i, flag in enumerate(result["LINKFLAGS"]):
            if flag.startswith("-u "):
                result["LINKFLAGS"][i] = result["LINKFLAGS"][i].split(" ")
    return result


def _get_flags(data):
    flags = {}
    cflags = set(data.get("CFLAGS", []))
    cxxflags = set(data.get("CXXFLAGS", []))
    ccflags = set(cflags & cxxflags)
    flags['CCFLAGS'] = list(ccflags)
    flags['CXXFLAGS'] = list(cxxflags - ccflags)
    flags['CFLAGS'] = list(cflags - ccflags)
    flags['CPPDEFINES'] = data.get("CPPDEFINES", [])
    flags['LINKFLAGS'] = data.get("LINKFLAGS", [])
    flags['LIBS'] = data.get("STDLIBS", [])

    return flags


def get_mbed_flags(target):
    variant_dir = join(FRAMEWORK_DIR, "platformio", "variants")
    eix_config_file = join(variant_dir, "%s.eix" % target)
    if not isfile(join(variant_dir, "%s.eix" % target)):
        sys.stderr.write(
            "Cannot find configuration file for your board! "
            "Please read instructions here %s\n" % join(
                FRAMEWORK_DIR, "platformio", "README.txt"))
        env.Exit(1)
    return _get_flags(parse_eix_file(eix_config_file))


def get_mbed_dirs_data(src_dirs, ignore_dirs=[]):
    def _get_mbed_labels():

        labels = {
            "TARGET": [],
            "TOOLCHAIN": []
        }

        for f in env.get("CPPDEFINES"):
            if f.startswith("TARGET_"):
                labels['TARGET'].append(f[7:])
            elif f.startswith("TOOLCHAIN_"):
                labels['TOOLCHAIN'].append(f[10:])
        return labels

    result = {
        "inc_dirs": list(),
        "empty_dirs": list(),
        "src_dirs": list(),
        "other_dirs": list(),
        "linker_path": ""
    }

    mbed_labels = _get_mbed_labels()

    target_dirs = list()
    for src_dir in src_dirs:
        target_dirs.append(join(src_dir))
        for root, dirs, files in walk(src_dir):
            for d in copy(dirs):
                # print "Looking in", d, ignore_dirs
                istargetdir = d.startswith(
                    "TARGET_") and d[7:] not in mbed_labels['TARGET']
                istoolchaindir = d.startswith(
                    "TOOLCHAIN_") and d[10:] not in mbed_labels['TOOLCHAIN']
                if (istargetdir or istoolchaindir or
                        d == "TESTS" or d.startswith(".") or
                        d in ignore_dirs):
                    dirs.remove(d)
                else:
                    target_dirs.append(join(root, d))

    for d in target_dirs:
        files = [f for f in listdir(d) if isfile(join(d, f))]
        if not files:
            result['empty_dirs'].append(d)
            continue
        if (any(env.IsFileWithExt(f, SRC_BUILD_EXT) for f in files)):
            result['src_dirs'].append(d)
        elif (any(env.IsFileWithExt(f, SRC_HEADER_EXT) for f in files)):
            result['inc_dirs'].append(d)
        else:
            result['other_dirs'].append(d)
        if "TOOLCHAIN_GCC_ARM" in d:
            for f in listdir(d):
                if f.lower().endswith(".ld"):
                    result['linker_path'] = join(d, f)
    return result


def _find_soft_device_hex(target_dirs):

    if not isfile(TARGETS_FILE):
        print("Warning! Cannot find \"targets.json\"."
              "Firmware will be linked without softdevice binary!")

    with open(TARGETS_FILE) as fp:
        data = json.load(fp)

    def _find_hex(target_name):
        assert isinstance(data, dict)
        if target_name not in data:
            return None
        target = data[target_name]
        if "EXPECTED_SOFTDEVICES_WITH_OFFSETS" not in target:
            try:
                return _find_hex(target.get("inherits", [])[0])
            except IndexError:
                return None
        else:
            return target['EXPECTED_SOFTDEVICES_WITH_OFFSETS'][0]['name']

    softdevice_file = _find_hex(variant)
    search_paths = target_dirs.get("other_dirs") + target_dirs.get(
        "inc_dirs") + target_dirs.get("src_dirs")
    if softdevice_file:
        for d in search_paths:
            if softdevice_file in listdir(d):
                return join(d, softdevice_file)

    sys.stderr.write(
        "Error: Cannot find SoftDevice binary file for your board!\n")
    env.Exit(1)

board_type = env.subst("$BOARD")
variant = MBED_VARIANTS[
    board_type] if board_type in MBED_VARIANTS else board_type.upper()

mbed_flags = get_mbed_flags(variant)


env.Replace(
    AS="$CC", ASCOM="$ASPPCOM",
    ASFLAGS=mbed_flags.get("CCFLAGS", [])[:],
    CCFLAGS=mbed_flags.get("CCFLAGS", []),
    CFLAGS=mbed_flags.get("CFLAGS", []),
    CXXFLAGS=mbed_flags.get("CXXFLAGS", []),
    LINKFLAGS=mbed_flags.get("LINKFLAGS", []),
    LIBS=mbed_flags.get("LIBS", []),
    CPPDEFINES=[define for define in mbed_flags.get("CPPDEFINES", [])]
)

env.Append(CFLAGS=CFLAGS)
env.Append(CXXFLAGS=CXXFLAGS)

env.Append(LIBS=["c"])  # temporary fix for the linker issue

# restore external build flags
if "build.extra_flags" in env.BoardConfig():
    env.ProcessFlags(env.BoardConfig().get("build.extra_flags"))
# remove base flags
env.ProcessUnFlags(env.get("BUILD_UNFLAGS"))
# apply user flags
env.ProcessFlags(env.get("BUILD_FLAGS"))


env.Append(CPPPATH=CPPPATH)

if board_type == "nrf51_dk":
    target_dirs = get_mbed_dirs_data(TARGETS_DIRS, ["TARGET_MCU_NRF51822"])
else:
    target_dirs = get_mbed_dirs_data(TARGETS_DIRS)

for inc_dir in target_dirs.get("inc_dirs", []):
    env.Append(CPPPATH=[inc_dir])

src_filter = ["+<*.[sS]>", "+<*.c*>"]
for src_dir in target_dirs.get("src_dirs", []):
    var_dir = join("$BUILD_DIR", "FrameworkMbed-{0}-{1}".format(
        basename(src_dir), md5(src_dir).hexdigest()[:5]))
    env.BuildSources(var_dir, src_dir, src_filter=src_filter)
    env.Append(CPPPATH=[src_dir])

env.Replace(LDSCRIPT_PATH=target_dirs.get("linker_path", ""))

if not env.get("LDSCRIPT_PATH"):
    sys.stderr.write("Cannot find linker script for your board!\n")
    env.Exit(1)

if env.get("PIOPLATFORM") == "nordicnrf51":
    env.Append(SOFTDEVICEHEX=_find_soft_device_hex(target_dirs))

env.BuildSources(*HAL_COMMON)


# Library processing
for lib_path in LIBS_DIRS:

    lib_manifest = {
        "name": "mbed-" + basename(lib_path),
        "build": {
            "flags": [],
            "srcFilter": []
        }
    }

    target_dirs = get_mbed_dirs_data([lib_path])
    lib_dirs = target_dirs.get("empty_dirs") + target_dirs.get(
        "inc_dirs") + target_dirs.get("src_dirs")

    for d in lib_dirs:
        if basename(lib_path) == "net" and "cellular" in d:
            continue
        rel_path = relpath(d, lib_path).replace("\\", "/")
        lib_manifest['build']['flags'].append("-I %s" % rel_path)
        lib_manifest['build']['srcFilter'].extend([
            "+<%s/*.c*>" % rel_path,
            "+<%s/*.[sS]>" % rel_path
        ])

    env.Append(
        EXTRA_LIB_BUILDERS=[PlatformIOLibBuilder(env, lib_path, lib_manifest)])
