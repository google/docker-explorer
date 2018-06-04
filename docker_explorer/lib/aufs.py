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
"""Aufs Storage class."""

from __future__ import print_function, unicode_literals

import glob
import json
import os

from docker_explorer.lib import storage


class ContainerNotFoundException(Exception):
  """Raised when no container could be found."""


class AufsStorage(storage.Storage):
  """This class implements AuFS storage specific methods."""

  STORAGE_METHOD = 'aufs'

  def __init__(self, docker_directory='/var/lib/docker', docker_version=2):
    """Initializes the AufsStorage class.

    Args:
      docker_directory (str): Path to the Docker root directory.
      docker_version (int): Docker storage version.
    """

    super(AufsStorage, self).__init__(
        docker_directory=docker_directory, docker_version=docker_version)

  def FindContainerId(self, partial_id):
    """Finds the path to a container ID from the first few characters.

    Args:
      partial_id (str): the first foew characters of a container ID.

    Returns:
      str: the path to the found container, or None is none was found.

    Raises:
      ContainerNotFoundException: if we found anything else but one matching
        container ID.
    """

    if self.docker_version == 1:
      glob_path = os.path.join(
          self.docker_directory, self.STORAGE_METHOD, 'layers',
          partial_id + '*')
    elif self.docker_version == 2:
      glob_path = os.path.join(self.containers_directory, partial_id + '*')
    possible_paths = [
        c for c in glob.glob(glob_path) if not c.endswith('-init')]
    if not possible_paths:
      raise ContainerNotFoundException(
          'Couldn\'t find container matching %s' % glob_path)
    elif len(possible_paths) == 1:
      return os.path.basename(possible_paths[0])
    else:
      error_msg = 'Too many possible containers matching %s' % glob_path
      for path in possible_paths:
        error_msg += '\t' + path
      raise ContainerNotFoundException(error_msg)

  def GetImageInfo(self, image_id):
    """Returns a docker image information from the image repository.

    Args:
      image_id (str): the ID of the docker image.

    Returns:
      str: the container's info.
    """
    if self.docker_version == 2:
      # TODO(romaing) implement for Docker storage V2.
      pass
    repo_path = os.path.join(self.docker_directory, 'repositories-aufs')
    with open(repo_path) as repo:
      repos_dict = json.load(repo)
      image_info = repos_dict['Repositories']
      for name, versions in image_info.items():
        for version, sha in versions.items():
          if sha == image_id:
            return '{0:s}:{1:s}'.format(name, version)
    return 'not found'

  def MakeMountCommands(self, container_id, mount_dir):
    """Generates the required shell commands to mount a container's ID.

    Args:
      container_id (str): the container ID to mount.
      mount_dir (str): the path to the target mount point.

    Returns:
      list: a list commands that needs to be run to mount the container's view
        of the file system.
    """
    if not os.path.isfile('/sbin/mount.aufs'):
      print('Could not find /sbin/mount.aufs. Please install the aufs-tools '
            'package.')

    container_info = self.GetContainer(container_id)
    mount_id = container_info.mount_id

    container_layers_filepath = os.path.join(
        self.docker_directory, self.STORAGE_METHOD, 'layers', mount_id)
    container_id = os.path.join(
        self.docker_directory, self.STORAGE_METHOD, 'diff', mount_id)
    if self.docker_version == 1:
      container_layers_filepath = os.path.join(
          self.docker_directory, self.STORAGE_METHOD, 'layers', container_id)

    commands = []
    mountpoint_path = os.path.join(
        self.docker_directory, self.STORAGE_METHOD, 'diff', container_id)
    commands.append('mount -t aufs -o ro,br={0:s}=ro+wh none {1:s}'.format(
        mountpoint_path, mount_dir))
    with open(container_layers_filepath) as container_layers_file:
      layers = container_layers_file.read().split()
      for layer in layers:
        mountpoint_path = os.path.join(
            self.docker_directory, self.STORAGE_METHOD, 'diff', layer)
        commands.append(
            'mount -t aufs -o ro,remount,append:{0:s}=ro+wh none {1:s}'.format(
                mountpoint_path, mount_dir))

    commands.extend(self._MakeExtraVolumeCommands(container_info, mount_dir))

    return commands
