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

from __future__ import unicode_literals

import json
import os

import docker_explorer
from docker_explorer import errors


class BaseStorage:
  """This class provides tools to list and access containers metadata.

  Every method provided is agnostic of the implementation used (AuFS,
  btrfs, etc.).
  """

  def __init__(
      self, docker_directory=docker_explorer.DEFAULT_DOCKER_DIRECTORY,
      docker_version=2):
    """Initializes a BaseStorage object.

    Args:
      docker_directory (str): Path to the Docker root directory.
      docker_version (int): Docker storage version.

    Raises:
      BadStorageException: when the underlying storage engine is unsupported.
    """
    if docker_version not in [1, 2]:
      error_message = f'Unsupported Docker version number {docker_version}'
      raise errors.BadStorageException(error_message)

    self.docker_version = docker_version
    self.storage_name = None
    self.root_directory = os.path.abspath(os.path.join(docker_directory, '..'))
    self.docker_directory = docker_directory

    self.containers_directory = os.path.join(docker_directory, 'containers')
    self.container_config_filename = 'config.v2.json'
    if self.docker_version == 1:
      self.container_config_filename = 'config.json'

  def MakeMountCommands(self, container_object, mount_dir):
    """Generates the required shell commands to mount a container given its ID.

    Args:
      container_object (Container): the container object to mount.
      mount_dir (str): the path to the target mount point.

    Raises:
      NotImplementedError: if this method is not implemented.
    """
    raise NotImplementedError('Please implement MakeMountCommands()')

  def _MakeVolumeMountCommands(self, container_object, mount_dir):
    """Generates the shell command to mount external Volumes if present.

    Args:
      container_object (Container): the container object.
      mount_dir (str): the destination mount_point.

    Returns:
      list(list(str)): a list of extra commands, or the empty list if no volume
        is to be mounted. Commands are list(str).
    """
    extra_commands = []
    mount_points = container_object.GetMountpoints()
    if self.docker_version == 1:
      # 'Volumes'
      for source, destination in mount_points:
        storage_path = os.path.join(self.root_directory, source)
        extra_commands.append(
            ['/bin/mount', '--bind', '-o', 'ro', storage_path, destination]
        )
    elif self.docker_version == 2:
      for source, destination in mount_points:
        storage_path = os.path.join(self.root_directory, source)
        volume_mountpoint = os.path.join(mount_dir, destination)
        extra_commands.append(
            ['/bin/mount', '--bind', '-o', 'ro', storage_path,
             volume_mountpoint])

    return extra_commands


class AufsStorage(BaseStorage):
  """This class implements AuFS storage specific methods."""

  STORAGE_METHOD = 'aufs'

  def MakeMountCommands(self, container_object, mount_dir):
    """Generates the required shell commands to mount a container given its ID.

    Args:
      container_object (Container): the container object to mount.
      mount_dir (str): the path to the target mount point.

    Returns:
      list(list(str)): a list commands that needs to be run to mount the
        container's view of the file system. Commands to run are list(str).
    """

    mount_id = container_object.mount_id

    if self.docker_version == 2:
      container_layers_filepath = os.path.join(
          self.docker_directory, self.STORAGE_METHOD, 'layers', mount_id)
      layer_id = os.path.join(
          self.docker_directory, self.STORAGE_METHOD, 'diff', mount_id)
    if self.docker_version == 1:
      layer_id = container_object.container_id

      container_layers_filepath = os.path.join(
          self.docker_directory, self.STORAGE_METHOD, 'layers', layer_id)

    commands = []
    mountpoint_path = os.path.join(
        self.docker_directory, self.STORAGE_METHOD, 'diff', layer_id)
    commands.append(
        ['/bin/mount', '-t', 'aufs', '-o',
         f'ro,br={mountpoint_path}=ro+wh', 'none', mount_dir])

    with open(
        container_layers_filepath, encoding='utf-8') as container_layers_file:
      layers = container_layers_file.read().split()
      for layer in layers:
        mountpoint_path = os.path.join(
            self.docker_directory, self.STORAGE_METHOD, 'diff', layer)
        commands.append(
            ['/bin/mount', '-t', 'aufs', '-o',
             f'ro,remount,append:{mountpoint_path}=ro+wh', 'none', mount_dir])

    # Adding the commands to mount any extra declared Volumes and Mounts
    commands.extend(self._MakeVolumeMountCommands(container_object, mount_dir))

    return commands


class OverlayStorage(BaseStorage):
  """This class implements OverlayFS storage specific methods."""

  STORAGE_METHOD = 'overlay'
  LOWERDIR_NAME = 'lower-id'
  UPPERDIR_NAME = 'upper'

  def _BuildLowerLayers(self, lower_content):
    """Builds the OverlayFS mount argument for the lower layer.

    Args:
      lower_content (str): content of the 'lower directory' description file.

    Returns:
      str: the mount.overlay command argument for the 'lower directory'.
    """
    # For overlay driver, this is only the full path to the lowerdir.
    return os.path.join(
        self.docker_directory, self.STORAGE_METHOD, lower_content, 'root')

  def MakeMountCommands(self, container_object, mount_dir):
    """Generates the required shell commands to mount a container given its ID.

    Args:
      container_object (Container): the container object.
      mount_dir (str): the path to the target mount point.

    Returns:
      list(list(str)): a list commands that needs to be run to mount the
        container's view of the file system. Commands to run are list(str).
    """
    mount_id_path = os.path.join(
        self.docker_directory, self.STORAGE_METHOD, container_object.mount_id)

    lowerdir_path = os.path.join(mount_id_path, self.LOWERDIR_NAME)
    with open(lowerdir_path, encoding='utf-8') as lower_fd:
      lower_dir = self._BuildLowerLayers(lower_fd.read().strip())
    upper_dir = os.path.join(mount_id_path, self.UPPERDIR_NAME)

    commands = [[
        '/bin/mount', '-t', 'overlay', 'overlay', '-o',
        f'ro,lowerdir={upper_dir}:{lower_dir}', mount_dir]]

    # Adding the commands to mount any extra declared Volumes and Mounts
    commands.extend(self._MakeVolumeMountCommands(container_object, mount_dir))
    return commands


class Overlay2Storage(OverlayStorage):
  """A specialization for Overlay2.

  See a description at
  https://docs.docker.com/storage/storagedriver/overlayfs-driver/#how-the-overlay2-driver-works.
  """

  STORAGE_METHOD = 'overlay2'
  LOWERDIR_NAME = 'lower'
  UPPERDIR_NAME = 'diff'

  def _BuildLowerLayers(self, lower_content):
    """Builds the OverlayFS mount argument for the lower layer.

    Args:
      lower_content (str): content of the 'lower directory' description file.

    Returns:
      str: the mount.overlay command argument for the 'lower directory'.
    """
    # For the overlay2 driver, the pointer to the 'lower directory' can be
    # made of multiple layers.
    # For that argument to be passed to the mount.overlay command, we need to
    # reconstruct full paths to all these layers.
    # ie: from 'abcd:0123' to '/var/lib/docker/abcd:/var/lib/docker/0123'
    lower_dir = ':'.join([
        os.path.join(self.docker_directory, self.STORAGE_METHOD, lower_)
        for lower_ in lower_content.split(':')
    ])
    return lower_dir


class WindowsFilterStorage(BaseStorage):
  """This class implements windowsfilter storage specific methods."""

  STORAGE_METHOD = 'windowsfilter'

  def MakeMountCommands(self, container_object, mount_dir):
    """Generates the required shell commands to merges a container's writeable
    sandbox.vhdx layer with its parent image's blank-base.vhdx layer,
    producing a mountable raw disk image.

    Note this differs from the other storage types which generate commands to
    directly mount the container FS.

    Args:
      container_object (Container): the container object to mount.
      mount_dir (str): Unused.

    Returns:
      list(list(str)): a list of commands to merge the target container's
        writable layer with it's parent images base. Commands to run are
        list(str).
    """
    windowsfilter_path = os.path.join(
      self.docker_directory, self.STORAGE_METHOD)
    layerchain_path = os.path.join(
      windowsfilter_path, container_object.mount_id, 'layerchain.json')

    with open(layerchain_path, encoding='utf-8') as layerchain_fd:
      layerchain_json = json.loads(layerchain_fd.read())
    # The top layer always contains the parent blank-base.vhdx disk
    parent_mount_id = layerchain_json[-1].split('\\')[-1]

    blank_base_path = os.path.join(
      windowsfilter_path, parent_mount_id, 'blank-base.vhdx')
    sandbox_path = os.path.join(
      windowsfilter_path, container_object.mount_id, 'sandbox.vhdx')

    commands = []
    commands.append(
      ['merge_vhdx.py', '--parent_disk', blank_base_path, '--child_disk',
      sandbox_path, '--out_image', f'{container_object.mount_id}.raw'])
    return commands
