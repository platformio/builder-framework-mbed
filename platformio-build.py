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
import warnings
from shutil import copyfile
from os import makedirs
from os.path import basename, isabs, isdir, isfile, join

from SCons.Script import COMMAND_LINE_TARGETS, Builder, DefaultEnvironment

from platformio import util
from platformio.builder.tools.piolib import PlatformIOLibBuilder

env = DefaultEnvironment()
platform = env.PioPlatform()
board = env.BoardConfig()

FRAMEWORK_DIR = platform.get_package_dir("framework-mbed")
assert isdir(FRAMEWORK_DIR)

# Be sure that the packages and tools paths are in the search path
warnings.simplefilter("ignore")
sys.path.insert(
    0, join(FRAMEWORK_DIR, "platformio", "package_deps",
            "py%d" % sys.version_info.major))
sys.path.insert(1, FRAMEWORK_DIR)

from pio_mbed_adapter import PlatformioMbedAdapter


# Long paths Windows hook
if "windows" in util.get_systype():
    from ctypes import create_unicode_buffer, windll, wintypes
    _GetShortPathNameW = windll.kernel32.GetShortPathNameW
    _GetShortPathNameW.argtypes = [
        wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    _GetShortPathNameW.restype = wintypes.DWORD


def shorten_path(path):
    output_buf_size = 0
    while True:
        output_buf = create_unicode_buffer(output_buf_size)
        needed = _GetShortPathNameW(path, output_buf, output_buf_size)
        if output_buf_size >= needed:
            return output_buf.value
        else:
            output_buf_size = needed


def process_path(dirs):
    result = []
    for d in dirs:
        path = join(FRAMEWORK_DIR, d)
        if ("windows" in util.get_systype()
                and "idedata" not in COMMAND_LINE_TARGETS):
            result.append(shorten_path(path))
        else:
            result.append(path)

    return result


def get_dynamic_manifest(lib_path):

    def _fix_paths(paths, lib_path):
        result = []
        for p in paths:
            fixed_path = p.replace(
                join("features", "unsupported", basename(lib_path), ""), "")
            result.append(fixed_path)
        return result

    lib_processor = PlatformioMbedAdapter(
        [lib_path],
        env.subst("$PROJECTSRC_DIR"),
        get_mbed_target(env.subst("$BOARD")),
        FRAMEWORK_DIR
    )

    config = lib_processor.extract_project_info(generate_config=False)
    src_files = _fix_paths(config.get("src_files"), lib_path)

    inc_dirs = [join(FRAMEWORK_DIR, d).replace("\\", "/") for d in config.get(
        "inc_dirs") if not isabs(d)]

    name = basename(lib_path)

    manifest = {
        "name": "mbed-" + name,
        "build": {
            "flags": ["-I."],
            "srcFilter": ["-<*>"],
            "libArchive": False
        }
    }

    if inc_dirs:
        extra_script = join(env.subst("$BUILD_DIR"), name + "_extra_script.py")
        manifest['build']['extraScript'] = extra_script.replace("\\", "/")
        if not isfile(extra_script):
            with open(extra_script, "w") as fp:
                fp.write("Import('env')\n")
                fp.write(
                    "env.Prepend(CPPPATH=[%s])" % ("'" + "', '".join(inc_dirs) + "'"))

    for f in src_files:
        manifest['build']['srcFilter'].extend([" +<%s>" % f])

    return manifest


def get_mbed_target(board_type):
    variants_remap = util.load_json(
        join(FRAMEWORK_DIR, "platformio", "variants_remap.json"))
    variant = variants_remap[
        board_type] if board_type in variants_remap else board_type.upper()
    return board.get("build.mbed_variant", variant)


def get_build_profile(cpp_defines):
    if "MBED_BUILD_PROFILE_RELEASE" in cpp_defines:
        return "release"
    elif "MBED_BUILD_PROFILE_DEBUG" in cpp_defines:
        return "debug"
    else:
        return "develop"

#
# Print warnings about deprecated flags
#

cpp_defines = env.Flatten(env.get("CPPDEFINES", []))
for f in ("PIO_FRAMEWORK_MBED_FILESYSTEM_PRESENT",
          "PIO_FRAMEWORK_MBED_EVENTS_PRESENT"):
    if f in cpp_defines:
        print("Warning! %s option "
              "is now obsolete. Please use mbed_app.json configuration file "
              "and/or a standalone library!" % f)

src_paths = [
    join(FRAMEWORK_DIR, "drivers"),
    join(FRAMEWORK_DIR, "events"),
    join(FRAMEWORK_DIR, "hal"),
    join(FRAMEWORK_DIR, "platform"),
    join(FRAMEWORK_DIR, "targets")
]

MBED_RTOS = "PIO_FRAMEWORK_MBED_RTOS_PRESENT" in env.Flatten(
    env.get("CPPDEFINES", []))

if MBED_RTOS:
    src_paths.extend([
        join(FRAMEWORK_DIR, "cmsis"),
        join(FRAMEWORK_DIR, "components"),
        join(FRAMEWORK_DIR, "features"),
        join(FRAMEWORK_DIR, "rtos")
    ])

else:
    # in mbed 2 only cmsis headers used
    env.Append(
        CPPPATH=[join(FRAMEWORK_DIR, "cmsis", "TARGET_CORTEX_M")]
    )


if not isdir(env.subst("$BUILD_DIR")):
    makedirs(env.subst("$BUILD_DIR"))

app_config = join(env.subst("$PROJECT_DIR"), "mbed_app.json")
if not isfile(app_config):
    app_config = None

build_profile = get_build_profile(cpp_defines)

framework_processor = PlatformioMbedAdapter(
    src_paths,
    env.subst("$BUILD_DIR"),
    get_mbed_target(env.subst("$BOARD")),
    FRAMEWORK_DIR,
    app_config,
    build_profile,
    env.subst("$PROJECT_DIR")
)

try:
    print ("Collecting mbed sources...")
    configuration = framework_processor.extract_project_info(
        generate_config=True)
except Exception as exc:
    sys.stderr.write("mbed build API internal error\n")
    print (exc)
    env.Exit(1)

env.Replace(
    AS="$CC",
    ASCOM="$ASPPCOM"
)

env.Append(
    ASFLAGS=configuration.get("build_flags").get("asm"),
    CCFLAGS=configuration.get("build_flags").get("common"),
    CXXFLAGS=configuration.get("build_flags").get("cxx"),
    LINKFLAGS=configuration.get("build_flags").get("ld"),
    CPPDEFINES=configuration.get("build_symbols"),
    LIBS=configuration.get("libs") + configuration.get("syslibs"),
    CPPPATH=[FRAMEWORK_DIR, "$BUILD_DIR", "$PROJECTSRC_DIR"]
)

env.Append(
    ASFLAGS=env.get("CCFLAGS", [])[:],
    CPPPATH=process_path(configuration.get("inc_dirs")),
    LIBPATH=process_path(configuration.get("lib_paths")),
    CCFLAGS=["-include", "mbed_config.h"],
    LIBS=["c", "gcc"]   # Fixes linker issues in some cases
)

if "nordicnrf5" in env.get("PIOPLATFORM"):
    has_soft_device = len(configuration.get("hex")) > 0
    if has_soft_device:
        softdevice_hex_path = join(FRAMEWORK_DIR, configuration.get("hex")[0])
        if isfile(softdevice_hex_path):
            env.Append(SOFTDEVICEHEX=softdevice_hex_path)
        else:
            print("Warning! Cannot find softdevice binary"
                  "Firmware will be linked without it!")

#
# Linker requires preprocessing with link flags
#

if not board.get("build.ldscript", ""):
    ldscript = join(FRAMEWORK_DIR, configuration.get("ldscript", [])[0] or "")
    if board.get("build.mbed.ldscript", ""):
        ldscript = env.subst(board.get("build.mbed.ldscript"))
    if isfile(ldscript):
        linker_script = env.Command(
            join("$BUILD_DIR", "%s.link_script.ld" % basename(ldscript)),
            ldscript,
            env.VerboseAction(
                '%s -E -P $LINKFLAGS $SOURCE -o $TARGET' %
                env.subst("$GDB").replace("-gdb", "-cpp"),
                "Generating LD script $TARGET"))

        env.Depends("$BUILD_DIR/$PROGNAME$PROGSUFFIX", linker_script)
        env.Replace(LDSCRIPT_PATH=linker_script)
    else:
        print ("Warning! Couldn't find linker script file!")

#
# Compile core part
#

src_filter = "-<*>"
usb_dir = join("drivers", "source", "usb")
for f in configuration.get("src_files"):
    # Exclude USB related source files from mbed2 build as they contain
    # references to RTOS API which is also not included.
    if not MBED_RTOS and usb_dir in f:
        continue
    src_filter = src_filter + " +<%s>" % f

env.BuildSources(
    join("$BUILD_DIR", "FrameworkMbed"),
    FRAMEWORK_DIR, src_filter=src_filter
)

#
# mbed has its own independent merge process
#


def merge_firmwares(target, source, env):
    framework_processor.merge_apps(
        env.subst(source)[0],
        env.subst(target)[0]
    )

    # some boards (e.g. nrf51 modify the resulting firmware)
    if framework_processor.has_target_hook():
        firmware_file = env.subst(join("$BUILD_DIR", "${PROGNAME}.hex"))
        if not isfile(firmware_file):
            copyfile(env.subst(source)[0], firmware_file)

        framework_processor.apply_hook(
            env.subst(join("$BUILD_DIR/$PROGNAME$PROGSUFFIX")),
            firmware_file
        )

new_builders = env.get("BUILDERS", {})
new_builders["MergeHex"] = Builder(action=merge_firmwares, suffix=".hex")
env.Replace(BUILDERS=new_builders)

#
# Add legacy libs as standalone
#

if not MBED_RTOS:
    legacy_libs = (
        join(FRAMEWORK_DIR, "features", "unsupported", "dsp"),
        join(FRAMEWORK_DIR, "features", "unsupported", "rpc"),
        join(FRAMEWORK_DIR, "features", "unsupported", "USBDevice"),
        join(FRAMEWORK_DIR, "features", "unsupported", "USBHost")
    )

    for lib in legacy_libs:
        env.Append(EXTRA_LIB_BUILDERS=[
            PlatformIOLibBuilder(
                env, join(FRAMEWORK_DIR, lib),
                get_dynamic_manifest(lib))
        ])
