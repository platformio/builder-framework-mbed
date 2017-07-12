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
from os.path import basename, isdir, isfile, join

from SCons.Script import DefaultEnvironment

from platformio import util
from platformio.builder.tools.piolib import PlatformIOLibBuilder

env = DefaultEnvironment()

FRAMEWORK_DIR = env.PioPlatform().get_package_dir("framework-mbed")
assert isdir(FRAMEWORK_DIR)


class MbedLibBuilder(PlatformIOLibBuilder):
    # For cases when sources located not ony in "src" dir

    @property
    def src_dir(self):
        return self.path


def get_mbed_config(target):
    config_file = join(FRAMEWORK_DIR, "platformio", "variants", target,
                       target + ".json")
    if not isfile(config_file):
        sys.stderr.write("Cannot find the configuration file for your board! "
                         "Please read instructions here %s\n" % join(
                             FRAMEWORK_DIR, "platformio", "README.txt"))
        env.Exit(1)

    return util.load_json(config_file)


def get_dynamic_manifest(name, config, extra_inc_dirs=[]):
    manifest = {
        "name": "mbed-" + name,
        "build": {
            "flags": ["-I.."],
            "srcFilter": ["-<*>"],
            "libArchive": False
        }
    }

    manifest['build']['flags'].extend(
        ["-I %s" % d for d in config.get("inc_dirs")])

    for d in extra_inc_dirs:
        manifest['build']['flags'].extend(["-I %s" % d.replace("\\", "/")])

    src_files = config.get("c_sources") + \
        config.get("s_sources") + config.get("cpp_sources")
    for f in src_files:
        manifest['build']['srcFilter'].extend([" +<%s>" % f])

    if name == "LWIP":
        manifest['dependencies'] = {"mbed-events": "*"}

    return manifest


variants_remap = util.load_json(
    join(FRAMEWORK_DIR, "platformio", "variants_remap.json"))
board_type = env.subst("$BOARD")
variant = variants_remap[
    board_type] if board_type in variants_remap else board_type.upper()

mbed_config = get_mbed_config(variant)

env.Replace(
    AS="$CC",
    ASCOM="$ASPPCOM",
    ASFLAGS=mbed_config.get("build_flags").get("asm") +
    mbed_config.get("build_flags").get("common"),
    CCFLAGS=mbed_config.get("build_flags").get("common"),
    CFLAGS=mbed_config.get("build_flags").get("c"),
    CXXFLAGS=mbed_config.get("build_flags").get("cxx"),
    LINKFLAGS=mbed_config.get("build_flags").get("ld"),
    LIBS=mbed_config.get("syslibs"))

symbols = []
for s in mbed_config.get("symbols"):
    s = s.replace("\"", "\\\"")
    macro = s.split("=", 1)
    if len(macro) == 2 and macro[1].isdigit():
        symbols.append((macro[0], int(macro[1])))
    else:
        symbols.append(s)

env.Replace(CPPDEFINES=symbols)

# restore external build flags
if "build.extra_flags" in env.BoardConfig():
    env.ProcessFlags(env.BoardConfig().get("build.extra_flags"))
# remove base flags
env.ProcessUnFlags(env.get("BUILD_UNFLAGS"))
# apply user flags
env.ProcessFlags(env.get("BUILD_FLAGS"))

MBED_RTOS = "PIO_FRAMEWORK_MBED_RTOS_PRESENT" in env.Flatten(
    env.get("CPPDEFINES", []))

if MBED_RTOS:
    env.Append(CPPDEFINES=["MBED_CONF_RTOS_PRESENT"])

#
# Process libraries
#

# There is no difference in processing between lib and feature
libs = mbed_config.get("libs").copy()
libs.update(mbed_config.get("features"))

if "PIO_FRAMEWORK_MBED_FILESYSTEM_PRESENT" in env.Flatten(
        env.get("CPPDEFINES", [])):
    env.Append(CPPDEFINES=["MBED_CONF_FILESYSTEM_PRESENT"])

# Add RTOS library only when a user requested it
if MBED_RTOS:
    rtos_config = mbed_config.get("libs").get("rtos")
    env.Append(EXTRA_LIB_BUILDERS=[
        MbedLibBuilder(env,
                       join(FRAMEWORK_DIR, rtos_config.get("dir")),
                       get_dynamic_manifest("rtos", rtos_config))
    ])

del libs['rtos']

for lib, lib_config in libs.items():
    extra_includes = []
    if lib == "events" and not MBED_RTOS:
        # Manually handle dependency on rtos lib
        extra_includes = [
            join(FRAMEWORK_DIR,
                 mbed_config.get("libs").get("rtos").get("dir"), f)
            for f in mbed_config.get("libs").get("rtos").get("inc_dirs")
        ]

    env.Append(EXTRA_LIB_BUILDERS=[
        MbedLibBuilder(env,
                       join(FRAMEWORK_DIR, lib_config.get("dir")),
                       get_dynamic_manifest(lib, lib_config, extra_includes))
    ])

#
# Process Core files from framework
#

env.Append(CPPPATH=[
    join(FRAMEWORK_DIR, d) for d in mbed_config.get("core").get("inc_dirs")
])

env.Append(CPPPATH=[
    FRAMEWORK_DIR,
    join(FRAMEWORK_DIR, "platformio", "variants", variant)
])

# If RTOS is enabled then some of the files from Core depdend on it
if MBED_RTOS:
    for d in mbed_config.get("libs").get("rtos").get("inc_dirs"):
        env.Append(CPPPATH=[join(FRAMEWORK_DIR, "rtos", d)])

core_src_files = mbed_config.get("core").get("s_sources") + mbed_config.get(
    "core").get("c_sources") + mbed_config.get("core").get("cpp_sources")

env.BuildSources(
    join("$BUILD_DIR", "FrameworkMbedCore"),
    FRAMEWORK_DIR,
    src_filter=["-<*>"] + [" +<%s>" % f for f in core_src_files])


if "nordicnrf5" in env.get("PIOPLATFORM"):
    softdevice_hex_path = join(FRAMEWORK_DIR,
                               mbed_config.get("softdevice_hex", ""))
    if softdevice_hex_path and isfile(softdevice_hex_path):
        env.Append(SOFTDEVICEHEX=softdevice_hex_path)
    else:
        print("Warning! Cannot find softdevice binary"
              "Firmware will be linked without it!")

#
# Generate linker script
#

env.Replace(LDSCRIPT_PATH=join(FRAMEWORK_DIR, mbed_config.get("ldscript")))
if not env.get("LDSCRIPT_PATH"):
    sys.stderr.write("Cannot find linker script for your board!\n")
    env.Exit(1)

linker_script = env.Command(
    join("$BUILD_DIR",
         "%s.link_script.ld" % basename(env.get("LDSCRIPT_PATH"))),
    env.get("LDSCRIPT_PATH"),
    env.VerboseAction("arm-none-eabi-cpp -E -P %s $SOURCE -o $TARGET" %
                      " ".join(mbed_config.get("build_flags").get("ld")),
                      "Generating LD script $TARGET"))

env.Depends("$BUILD_DIR/$PROGNAME$PROGSUFFIX", linker_script)
env.Replace(LDSCRIPT_PATH=linker_script)
