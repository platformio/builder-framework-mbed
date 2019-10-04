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

from os.path import basename, join

from tools.resources import Resources


class MbedResourcesFixedPath(Resources):

    def __init__(self, framework_path, notify, collect_ignores=False):
        super(MbedResourcesFixedPath, self).__init__(notify, collect_ignores)
        self.framework_path = framework_path

    def get_file_paths(self, file_type):
        return self.fix_paths(self._get_from_refs(file_type, lambda f: f.path))

    def fix_path(self, path):
        # mbed build api provides the relative path with two
        # redundant directories, so they are removed
        if not path:
            return ""

        framework_dir = basename(self.framework_path)
        if framework_dir in path:
            fixed_path = path[path.index(framework_dir) + len(framework_dir):]
            return fixed_path[1:]

        return join(self.framework_path, path)

    def fix_paths(self, paths):
        result = []
        for path in paths:
            path = self.fix_path(path)
            if not path:
                continue
            result.append(path)

        return result
