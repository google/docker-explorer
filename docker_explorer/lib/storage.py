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
"""Base class for a Docker BaseStorage object."""

from __future__ import print_function, unicode_literals

import os
import subprocess
import sys

from docker_explorer.lib import utils


class BaseStorage(object):
  """This class provides tools to list and access containers metadata.

  Every method provided is agnostic of the implementation used (AuFS,
  btrfs, etc.).
  """

  def __init__(self, docker_directory='/var/lib/docker', docker_version=2):
    """Initialized a BaseStorage object.

    Args:
      docker_directory (str): Path to the Docker root directory.
      docker_version (int): Docker storage version.
    """
    if docker_version not in [1, 2]:
      print('Unsupported Docker version number {0:d}'.format(docker_version))
      sys.exit(1)

    self.docker_version = docker_version
    self.storage_name = None
    self.root_directory = os.path.abspath(os.path.join(docker_directory, '..'))
    self.docker_directory = docker_directory

    self.containers_directory = os.path.join(docker_directory, 'containers')
    self.container_config_filename = 'config.v2.json'
    if self.docker_version == 1:
      self.container_config_filename = 'config.json'

  def ShowRepositories(self):
    """Returns information about the images in the Docker repository.

    Returns:
      str: human readable information about image repositories.
    """
    repositories_file_path = os.path.join(
        self.docker_directory, 'image', self.STORAGE_METHOD,
        'repositories.json')
    if self.docker_version == 1:
      repositories_file_path = os.path.join(
          self.docker_directory, 'repositories-aufs')
    result_string = (
        'Listing repositories from file {0:s}').format(repositories_file_path)
    with open(repositories_file_path) as rf:
      repositories_string = rf.read()
    return result_string + utils.PrettyPrintJSON(repositories_string)

  def MakeMountCommands(self, container_object, mount_dir):
    """Generates the required shell commands to mount a container's ID.

    Args:
      container_object (Container): the container object to mount.
      mount_dir (str): the path to the target mount point.

    Raises:
      NotImplementedError: if this method is not implemented.
    """
    raise NotImplementedError('Please implement MakeMountCommands()')

  def _MakeExtraVolumeCommands(self, container_object, mount_dir):
    """Generates the shell command to mount external Volumes if present.

    Args:
      container_object (Container): the container object.
      mount_dir (str): the destination mount_point.

    Returns:
      list(str): a list of extra commands, or the empty list if no volume is to
        be mounted.
    """
    extra_commands = []
    if self.docker_version == 1:
      # 'Volumes'
      container_volumes = container_object.volumes
      if container_volumes:
        for mountpoint, storage in container_volumes.items():
          mountpoint_ihp = mountpoint.lstrip(os.path.sep)
          storage_ihp = storage.lstrip(os.path.sep)
          storage_path = os.path.join(self.root_directory, storage_ihp)
          volume_mountpoint = os.path.join(mount_dir, mountpoint_ihp)
          extra_commands.append('mount --bind -o ro {0:s} {1:s}'.format(
              storage_path, volume_mountpoint))
    elif self.docker_version == 2:
      # 'MountPoints'
      container_mount_points = container_object.mount_points
      if container_mount_points:
        for _, storage_info in container_mount_points.items():
          src_mount_ihp = storage_info['Source']
          dst_mount_ihp = storage_info['Destination']
          src_mount = src_mount_ihp.lstrip(os.path.sep)
          dst_mount = dst_mount_ihp.lstrip(os.path.sep)
          if not src_mount:
            volume_name = storage_info['Name']
            src_mount = os.path.join('docker', 'volumes', volume_name, '_data')
          storage_path = os.path.join(self.root_directory, src_mount)
          volume_mountpoint = os.path.join(mount_dir, dst_mount)
          extra_commands.append('mount --bind -o ro {0:s} {1:s}'.format(
              storage_path, volume_mountpoint))

    return extra_commands

  def Mount(self, container_object, mount_dir):
    """Mounts the specified container's filesystem.

    Args:
      container_object (Container): the container.
      mount_dir (str): the path to the destination mount point
    """

    commands = self.MakeMountCommands(container_object, mount_dir)
    for c in commands:
      print(c)
    print('Do you want to mount this container Id: {0:s} on {1:s} ?\n'
          '(ie: run these commands) [Y/n]'.format(
              container_object.container_id, mount_dir))
    choice = raw_input().lower()
    if not choice or choice == 'y' or choice == 'yes':
      for c in commands:
        # TODO(romaing) this is quite unsafe, need to properly split args
        subprocess.call(c, shell=True)

class AufsStorage(BaseStorage):
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

  def MakeMountCommands(self, container_object, mount_dir):
    """Generates the required shell commands to mount a container's ID.

    Args:
      container_object (Container): the container object to mount.
      mount_dir (str): the path to the target mount point.

    Returns:
      list: a list commands that needs to be run to mount the container's view
        of the file system.
    """
    if not os.path.isfile('/sbin/mount.aufs'):
      print('Could not find /sbin/mount.aufs. Please install the aufs-tools '
            'package.')

    mount_id = container_object.mount_id

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

    commands.extend(self._MakeExtraVolumeCommands(container_object, mount_dir))

    return commands


class OverlayStorage(BaseStorage):
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

  def MakeMountCommands(self, container_object, mount_dir):
    """Generates the required shell commands to mount a container's ID.

    Args:
      container_object (Container): the container object.
      mount_dir (str): the path to the target mount point.

    Returns:
      list: a list commands that needs to be run to mount the container's view
        of the file system.
    """
    mount_id_path = os.path.join(
        self.docker_directory, self.STORAGE_METHOD, container_object.mount_id)

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
