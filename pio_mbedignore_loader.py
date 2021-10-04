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

from tools.resources import MbedIgnoreSet


class PioMbedignoreLoader(MbedIgnoreSet):
    """Loads ignore patterns from .mbedignore file

    It takes the path to the `.mbedignore` file in the constructor.
    The collect_ignore_patterns() will return the list of the patterns
    from the file. For each pattern the 'mbed-os/' or 'framework-mbed/' prefix
    will be removed if specified. Since originial MbedIgnoreSet computes
    relative paths starting from the first parent directory,
    the parent directory name will be removed, so e.g. paterrns:

        mbed-os/features/cellular/*
        framework-mbed/features/cellular/*
        features/cellular/*

    will be turned to:

        cellular/*

    """

    def __init__(self, mbedignore_path):
        self._mbedignore_path = mbedignore_path
        self._is_patterns_collected = False
        super().__init__()

    def collect_ignore_patterns(self):
        if self._is_patterns_collected:
            return self._ignore_patterns

        self._collect_patterns_from_mbedignore_file_and_save_them()
        self._remove_mbed_framework_prefix_from_patterns()
        self._remove_first_directory_name_from_patterns()
        self._remove_match_all_patterns()
        self._is_patterns_collected = True
        return self._ignore_patterns

    def _collect_patterns_from_mbedignore_file_and_save_them(self):
        try:
            self.add_mbedignore('.', self._mbedignore_path)
            print('Loaded .mbedignore patterns from: {}'.format(
                self._mbedignore_path))
        except FileNotFoundError:
            print('No .mbedignore found under {}'.format(
                self._mbedignore_path))

    def _remove_mbed_framework_prefix_from_patterns(self):
        paths_without_mbed_framework_prefix_iterator = map(
            lambda p: p.replace('mbed-os/', '').replace('framework-mbed/', ''),
            self._ignore_patterns)
        self._ignore_patterns = list(
            paths_without_mbed_framework_prefix_iterator)

    def _remove_first_directory_name_from_patterns(self):
        paths_without_first_directory_name_iterator = map(
            lambda p: p[p.find('/')+1:],
            self._ignore_patterns)
        self._ignore_patterns = list(
            paths_without_first_directory_name_iterator)

    def _remove_match_all_patterns(self):
        paths_without_match_all_patterns_iterator = filter(
            lambda p: p != '*',
            self._ignore_patterns)
        self._ignore_patterns = list(
            paths_without_match_all_patterns_iterator)
