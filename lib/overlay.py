# -*- coding: utf-8 -*-
# Copyright 2016 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""OverlayFS Storage class."""

from __future__ import unicode_literals

import os

from storage import Storage


class OverlayStorage(Storage):
  """This class implements OverlayFS storage specific methods."""

  STORAGE_METHOD = 'overlay'

  def MakeMountCommands(self, container_id, mount_dir):
    """Generates the required shell commands to mount a container's ID.

    Args:
      container_id (str): the container ID to mount.
      mount_dir (str): the path to the target mount point.

    Returns:
      list: a list commands that needs to be run to mount the container's view
        of the file system.
    """
    container_info = self.GetContainerInfo(container_id)
    mount_id_path = os.path.join(
        self.docker_directory, self.STORAGE_METHOD, container_info.mount_id)

    with open(os.path.join(mount_id_path, 'lower-id')) as lower_fd:
      lower_dir = os.path.join(
          self.docker_directory, self.STORAGE_METHOD, lower_fd.read().strip(),
          'root')
    upper_dir = os.path.join(mount_id_path, 'upper')
    work_dir = os.path.join(mount_id_path, 'work')

    cmd = (
        'mount -t overlay overlay -o ro,lowerdir=\"{0:s}\":"{1:s}\",'
        'workdir="{2:s}\" \"{3:s}\"').format(
            lower_dir, upper_dir, work_dir, mount_dir)
    return [cmd]
