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

from docker_explorer.lib import storage


class OverlayStorage(storage.Storage):
  """This class implements OverlayFS storage specific methods."""

  STORAGE_METHOD = 'overlay'
  LOWER_NAME = u'lower-id'
  UPPER_NAME = u'upper'

  def _BuildLowerLayers(self, lower):
    """Builds the mount command option for the 'lower' directory.

    Args:
      lower (str): the path to the lower directory.

    Returns:
      str: the mount command option for thr 'lower' directory.
    """
    return os.path.join(
        self.docker_directory, self.STORAGE_METHOD, lower.strip(), 'root')

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

    with open(os.path.join(mount_id_path, self.LOWER_NAME)) as lower_fd:
      lower_dir = self._BuildLowerLayers(lower_fd.read())
    upper_dir = os.path.join(mount_id_path, self.UPPER_NAME)
    work_dir = os.path.join(mount_id_path, 'work')

    cmd = (
        'mount -t overlay overlay -o ro,lowerdir=\"{0:s}\":"{1:s}\",'
        'workdir="{2:s}\" \"{3:s}\"').format(
            lower_dir, upper_dir, work_dir, mount_dir)
    return [cmd]


class Overlay2Storage(OverlayStorage):
  """A specialization for Overlay2.

  See a description at
  https://docs.docker.com/storage/storagedriver/overlayfs-driver/#how-the-overlay2-driver-works.
  """

  STORAGE_METHOD = u'overlay2'
  LOWER_NAME = u'lower'
  UPPER_NAME = u'diff'

  def _BuildLowerLayers(self, lower):
    """Builds the mount command option for the 'lower' directory.

    Args:
      lower (str): the path to the lower directory.

    Returns:
      str: the mount command option for thr 'lower' directory.
    """
    # We need the full pathname to the lower directory.
    # If multiple lower directories are stacked, we process each of them
    # separately.
    lower_dir = ':'.join([
        os.path.join(self.docker_directory, self.STORAGE_METHOD, lower_)
        for lower_ in lower.strip().split(':')
    ])
    return lower_dir
