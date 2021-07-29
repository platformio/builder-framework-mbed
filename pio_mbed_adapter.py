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


import json
import sys
import os

from os.path import (abspath, basename, isfile, join, relpath,
                     normpath)

from tools.build_api import prepare_toolchain, UPDATE_WHITELIST

from tools.regions import merge_region_list
from tools.targets import TARGET_MAP, Target, update_target_data
from tools.utils import generate_update_filename

from pio_mock_notifier import PlatformioFakeNotifier
from pio_resources_fixed_path import MbedResourcesFixedPath

# A handy global as PlatformIO supports only GCC toolchain
TOOLCHAIN_NAME = "GCC_ARM"
# Possible profiles: debug, develop, release
BUILD_PROFILE = "release"


def get_notifier():
    # Not used by PlatformIO, but requried by mbed build api internals.
    return PlatformioFakeNotifier()


class PlatformioMbedAdapter(object):
    def __init__(self,
                 src_paths,
                 build_path,
                 target,
                 framework_path,
                 app_config=None,
                 build_profile=BUILD_PROFILE,
                 custom_target_path=None,
                 toolchain_name=TOOLCHAIN_NAME,
                 ignore_dirs=None):
        self.src_paths = src_paths
        self.build_path = build_path
        self.target = target
        self.framework_path = framework_path
        self.app_config = app_config
        self.ignore_dirs = ignore_dirs
        self.toolchain_name = toolchain_name
        self.build_profile = build_profile
        self.toolchain = None
        self.resources = None
        self.notify = get_notifier()
        self.custom_target_path = custom_target_path

    def get_build_profile(self):
        file_with_profiles = join(self.framework_path, "tools", "profiles",
                                  "%s.json" % self.build_profile)
        if not isfile(file_with_profiles):
            sys.stderr.write("Could not find the file with build profiles!\n")
            sys.exit(1)
        profiles = []
        contents = json.load(open(file_with_profiles))
        profiles.append(contents)

        return profiles

    def get_target_config(self):
        target_info = TARGET_MAP.get(self.target, "")
        if not target_info:
            sys.stderr.write("Failed to extract configuration for %s.\n" % self.target)
            sys.stderr.write("It might not be supported in the this Mbed release.\n")
            sys.exit(1)

        return target_info

    def generate_mbed_config_file(self):
        self.toolchain.get_config_header()

    def process_symbols(self, symbols):
        result = []
        for s in symbols:
            if "MBED_BUILD_TIMESTAMP" in s:
                # Skip to avoid recompilation the entire project
                continue
            elif '"' in s and ".h" in s:
                # for cases with includes in value like:
                # CMSIS_VECTAB_VIRTUAL_HEADER_FILE="cmsis_nvic.h"
                s = s.replace('"', '\\"')

            result.append(s)

        # Symbols need to be sorted to avoid recompilation
        result.sort()
        return result

    def needs_merging(self):
        return self.toolchain.config.has_regions

    def merge_apps(self, userprog_path, firmware_path):
        if self.toolchain.config.has_regions:
            region_list = list(self.toolchain.config.regions)
            region_list = [
                r._replace(filename=userprog_path) if r.active else r for r in region_list
            ]

            merge_region_list(
                region_list,
                firmware_path,
                self.notify,
                restrict_size=self.toolchain.config.target.restrict_size
            )
            update_regions = [
                r for r in region_list if r.name in UPDATE_WHITELIST]

            if update_regions:
                update_res = join(
                    self.build_path,
                    generate_update_filename(
                        firmware_path, self.toolchain.target))
                merge_region_list(
                    update_regions,
                    update_res,
                    self.notify,
                    restrict_size=self.toolchain.config.target.restrict_size)
                firmware_path = (firmware_path, update_res)
            else:
                firmware_path = (firmware_path, None)


    def extract_project_info(self, generate_config=False):
        """Extract comprehensive information in order to build a PlatformIO project

        src_paths - a list of paths that contain needed files to build project
        build_path - a path where mbed_config.h will be created
        target - suitable mbed target name
        framework_path = path to the root folder of the mbed framework package
        app_config - path to mbed_app.json
        ignore_dirs - doesn't work with GCC at the moment?
        """
        # Default values for mbed build api functions
        if self.custom_target_path and isfile(
                join(self.custom_target_path, "custom_targets.json")):
            print ("Detected custom target file")
            Target.add_extra_targets(source_dir=self.custom_target_path)
            update_target_data()
        target = self.get_target_config()
        build_profile = self.get_build_profile()

        jobs = 1  # how many compilers we can run at once
        name = None  # the name of the project
        dependencies_paths = None  # libraries location to include when linking
        macros = None  # additional macros
        inc_dirs = None  # additional dirs where include files may be found
        ignore = self.ignore_dirs  # list of paths to add to mbedignore
        clean = False  # Rebuild everything if True

        # For cases when project and framework are on different
        # logic drives (Windows only)
        backup_cwd = os.getcwd()
        os.chdir(self.framework_path)

        # Convert src_path to a list if needed
        if not isinstance(self.src_paths, list):
            self.src_paths = [self.src_paths]
        self.src_paths = [relpath(s) for s in self.src_paths]

        # Pass all params to the unified prepare_toolchain()
        self.toolchain = prepare_toolchain(
            self.src_paths, self.build_path, target, self.toolchain_name,
            macros=macros, clean=clean, jobs=jobs, notify=self.notify,
            app_config=self.app_config, build_profile=build_profile,
            ignore=ignore)

        # The first path will give the name to the library
        if name is None:
            name = basename(normpath(abspath(self.src_paths[0])))

        # Disabled for legacy libraries
        # for src_path in self.src_paths:
        #     if not exists(src_path):
        #         error_msg = "The library src folder doesn't exist:%s", src_path
        #         raise Exception(error_msg)


        self.resources = MbedResourcesFixedPath(self.framework_path, self.notify).scan_with_toolchain(
            self.src_paths, self.toolchain, dependencies_paths,
            inc_dirs=inc_dirs)

        src_files = (
            self.resources.s_sources +
            self.resources.c_sources +
            self.resources.cpp_sources
        )

        if generate_config:
            self.generate_mbed_config_file()

        # Revert back project cwd
        os.chdir(backup_cwd)

        result = {
            "src_files": src_files,
            "inc_dirs": self.resources.inc_dirs,
            "ldscript": [self.resources.linker_script],
            "objs": self.resources.objects,
            "build_flags": {k: sorted(v) for k, v in self.toolchain.flags.items()},
            "libs": [basename(l) for l in self.resources.libraries],
            "lib_paths": self.resources.lib_dirs,
            "syslibs": self.toolchain.sys_libs,
            "build_symbols": self.process_symbols(
                self.toolchain.get_symbols()),
            "hex": self.resources.hex_files,
            "bin": self.resources.bin_files
        }

        return result

    def has_target_hook(self):
        return hasattr(self.toolchain.target, "post_binary_hook")

    def get_target_hook(self):
        if hasattr(self.toolchain.target, "post_binary_hook"):
            mdata = self.toolchain.target.get_module_data()
            hook_data = self.toolchain.target.post_binary_hook
            class_name, hook = hook_data["function"].split(".")
            cls = mdata[class_name]
            # hook is a function with the next signature:
            # def (toolchain, resources, path_elf, path_bin_or_hex)
            return getattr(cls, hook)
        else:
            return None

    def apply_hook(self, elf_path, firmware_path):
        hook = self.get_target_hook()
        if hook:
            hook(self.toolchain, self.resources, elf_path, firmware_path)
