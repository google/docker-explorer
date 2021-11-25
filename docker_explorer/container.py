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
"""Base class for a Docker Container object."""

from __future__ import unicode_literals

import collections
import json
import logging
import os
import subprocess

from docker_explorer import errors
from docker_explorer import storage
from docker_explorer import utils

logger = logging.getLogger('docker-explorer')


def GetAllContainersIDs(docker_root_directory):
  """Gets a list of containers IDs.

   Args:
     docker_root_directory(str): the path to the Docker root directory.
       ie: '/var/lib/docker'.

   Returns:
     list(str): the list of containers ID.

   Raises:
     errors.BadStorageException: If required files or directories are not found
       in the provided Docker directory.
  """
  if not os.path.isdir(docker_root_directory):
    raise errors.BadStorageException(
        f'Provided path is not a directory "{docker_root_directory}"')
  containers_directory = os.path.join(docker_root_directory, 'containers')

  if not os.path.isdir(containers_directory):
    raise errors.BadStorageException(
        f'Containers directory {containers_directory} does not exist')
  container_ids_list = os.listdir(containers_directory)

  return container_ids_list


class Container:
  """Implements methods to access information about a Docker container.

  Attributes:
    config_image_name (str): the name of the container's image (eg: 'busybox').
    config_labels (list(str)): labels attached to the container.
    container_id (str): the ID of the container.
    creation_timestamp (str): the container's creation timestamp.
    docker_version (int): the version number of the storage system.
    image_id (str): the ID of the container's image.
    mount_points (list(dict)): list of mount points to bind from host to the
      container. (Docker storage backend v2).
    name (str): the name of the container.
    running (boolean): True if the container is running.
    start_timestamp (str): the container's start timestamp.
    storage_name (str): the container's storage driver name.
    storage_object (BaseStorage): the container's storage backend object.
    upper_dir (str): path to upper_dir folder.
    volumes (list(tuple)): list of mount points to bind from host to the
      container. (Docker storage backend v1).
    exposed_ports (dict): list of exposed ports from the container
  """

  STORAGES_MAP = {
      'aufs': storage.AufsStorage,
      'overlay': storage.OverlayStorage,
      'overlay2': storage.Overlay2Storage,
      'windowsfilter': storage.WindowsFilterStorage
  }

  def __init__(self, docker_directory, container_id, docker_version=2):
    """Initializes the Container class.

    Args:
      docker_directory (str): the absolute path to the Docker directory.
      container_id (str): the container ID.
      docker_version (int): (Optional) the version of the Docker storage module.

    Raises:
      errors.BadContainerException: if there was an error when parsing
        container_info_json_path
    """
    self.docker_version = docker_version
    self.container_config_filename = 'config.v2.json'
    if self.docker_version == 1:
      self.container_config_filename = 'config.json'

    self.docker_directory = docker_directory

    container_info_json_path = os.path.join(
        self.docker_directory, 'containers', container_id,
        self.container_config_filename)

    if not os.path.isfile(container_info_json_path):
      raise errors.BadContainerException(
          'Unable to find container configuration file: '
          f'{container_info_json_path}'
      )
    with open(
        container_info_json_path, encoding='utf-8') as container_info_json_file:
      container_info_dict = json.load(container_info_json_file)

    if container_info_dict is None:
      raise errors.BadContainerException(
          'Could not load container configuration file: '
          f'{container_info_json_path}')

    self.container_id = container_info_dict.get('ID', None)

    # Parse the 'Config' key, which relates to the Image configuration
    self.config_image_name = self._GetConfigValue(container_info_dict, 'Image')
    self.config_labels = self._GetConfigValue(container_info_dict, 'Labels')
    self.creation_timestamp = container_info_dict.get('Created', None)
    self.image_id = container_info_dict.get('Image', None)
    self.mount_id = None
    self.mount_points = container_info_dict.get('MountPoints', None)
    self.name = container_info_dict.get('Name', '')
    json_state = container_info_dict.get('State', None)
    if json_state:
      self.running = json_state.get('Running', False)
      self.start_timestamp = json_state.get('StartedAt', False)
    self.storage_name = container_info_dict.get('Driver', None)
    if self.storage_name is None:
      raise errors.BadContainerException(
          f'{container_info_json_path} container config file lacks Driver key')
    self.upper_dir = None
    self.volumes = container_info_dict.get('Volumes', None)

    self.exposed_ports = self._GetConfigValue(
        container_info_dict, 'ExposedPorts')

    self._SetStorage(self.storage_name)

    if self.docker_version == 2:
      c_path = os.path.join(
          self.docker_directory, 'image', self.storage_name, 'layerdb',
          'mounts', container_id)
      mount_id_path = os.path.join(c_path, 'mount-id')
      with open(mount_id_path, encoding='utf-8') as mount_id_file:
        self.mount_id = mount_id_file.read()

    if self.storage_name in ['overlay', 'overlay2']:
      self.upper_dir = os.path.join(self.storage_object.docker_directory,
                                    self.storage_object.STORAGE_METHOD,
                                    self.mount_id,
                                    self.storage_object.UPPERDIR_NAME)

    self.log_path = container_info_dict.get('LogPath', None)

  def _GetConfigValue(
      self, configuration, key, default_value=None,
      ignore_container_config=False):
    """Returns the value of a configuration key in the parsed container file.

    Args:
      configuration(dict): the parsed state from the config.json file.
      key(str): the key we need the value from.
      default_value(object): what to return if the key can't be found.
      ignore_container_config(bool): whether or not to ignore the container's
        specific configuration (from the ContainerConfig) key.

    Returns:
      object: the extracted value.
    """
    image_config = configuration.get('Config', None)
    if not image_config:
      return default_value


    if not ignore_container_config:
      # If ContainerConfig has a different value for that key, return this one.
      container_config = configuration.get('ContainerConfig', None)
      if container_config:
        if key in container_config:
          return container_config.get(key, default_value)

    return image_config.get(key, default_value)

  def GetLayerSize(self, layer_id):
    """Returns the size of the layer.

    Args:
      layer_id (str): the layer ID to get the size of.

    Returns:
      int: the size of the layer in bytes.
    """
    size = 0
    if self.docker_version == 1:
      path = os.path.join(self.docker_directory, 'graph',
                          layer_id, 'layersize')
      with open(path, encoding='utf-8') as layer_file:
        size = int(layer_file.read())
    # TODO: Add docker storage v2 support
    return size

  def GetLayerInfo(self, layer_id):
    """Gets a docker FS layer information.

    Returns:
      dict: the layer information.
    """
    if self.docker_version == 1:
      layer_info_path = os.path.join(
          self.docker_directory, 'graph', layer_id, 'json')
    elif self.docker_version == 2:
      hash_method, layer_id = layer_id.split(':')
      layer_info_path = os.path.join(
          self.docker_directory, 'image', self.storage_name, 'imagedb',
          'content', hash_method, layer_id)
    if os.path.isfile(layer_info_path):
      with open(layer_info_path, encoding='utf-8') as layer_info_file:
        return json.load(layer_info_file)

    return None

  def GetOrderedLayers(self):
    """Returns an array of the sorted layer IDs for a container.

    Returns:
      list(str): a list of layer IDs.
    """
    layer_list = []
    current_layer = self.container_id
    layer_path = os.path.join(self.docker_directory, 'graph', current_layer)
    if not os.path.isdir(layer_path):
      current_layer = self.image_id

    while current_layer is not None:
      layer_list.append(current_layer)
      if self.docker_version == 1:
        layer_info_path = os.path.join(
            self.docker_directory, 'graph', current_layer, 'json')
        with open(layer_info_path, encoding='utf-8') as layer_info_file:
          layer_info = json.load(layer_info_file)
          current_layer = layer_info.get('parent', None)
      elif self.docker_version == 2:
        hash_method, layer_id = current_layer.split(':')
        parent_layer_path = os.path.join(
            self.docker_directory, 'image', self.storage_name, 'imagedb',
            'metadata', hash_method, layer_id, 'parent')
        if not os.path.isfile(parent_layer_path):
          break
        with open(parent_layer_path, encoding='utf-8') as parent_layer_file:
          current_layer = parent_layer_file.read().strip()

    return layer_list

  def GetHistory(self, show_empty_layers=False):
    """Returns a dict containing the modification history of the container.

    Args:
      show_empty_layers (bool): whether to display empty layers.
    Returns:
      dict: object describing history of the container.
    Raises:
      ValueError: when expected layer can't be found.
    """
    result_dict = {}
    for layer in self.GetOrderedLayers():
      layer_info = self.GetLayerInfo(layer)
      layer_dict = collections.OrderedDict()

      if layer is None:
        raise ValueError(f'Layer {layer} does not exist')

      layer_size = self.GetLayerSize(layer)
      if layer_size > 0 or show_empty_layers or self.docker_version == 2:
        layer_dict['created_at'] = utils.FormatDatetime(layer_info['created'])
        if 'container_config' in layer_info:
          container_cmd = layer_info['container_config'].get('Cmd', None)
          if container_cmd:
            layer_dict['container_cmd'] = ' '.join(container_cmd)
        comment = layer_info.get('comment', None)
        if comment:
          layer_dict['comment'] = comment

      layer_dict['size'] = layer_size
      result_dict[layer] = layer_dict

    return result_dict

  def GetMountpoints(self):
    """Returns the mount points & volumes for a container.

    Returns:
      list((str, str)): list of mount points (source_path, destination_path).
    """
    mount_points = []

    if self.docker_version == 1:
      if self.volumes:
        for source, destination in self.volumes.items():
          # Stripping leading '/' for easier joining later.
          source_path = source.lstrip(os.path.sep)
          destination_path = destination.lstrip(os.path.sep)
          mount_points.append((source_path, destination_path))

    elif self.docker_version == 2:
      if self.mount_points:
        for dst_mount_ihp, storage_info in self.mount_points.items():
          src_mount_ihp = None
          if 'Type' not in storage_info:
            # Let's do some guesswork
            if 'Source' in storage_info:
              storage_info['Type'] = 'volume'
            else:
              storage_info['Type'] = 'bind'

          if storage_info.get('Type') == 'bind':
            src_mount_ihp = storage_info['Source']

          elif storage_info.get('Type') == 'volume':
            volume_driver = storage_info.get('Driver')
            if storage_info.get('Driver') != 'local':
              logger.warning(
                  f'Unsupported driver "{volume_driver}" '
                  f'for volume "{dst_mount_ihp}"')
              continue
            volume_name = storage_info['Name']
            src_mount_ihp = os.path.join('volumes', volume_name, '_data')

          else:
            storage_type = storage_info.get('Type')
            logger.warning(
                f'Unsupported storage type "{storage_type}" '
                f'for Volume "{dst_mount_ihp}"')
            continue

          # Removing leading path separator, otherwise os.path.join is behaving
          # 'smartly' (read: 'terribly').
          src_mount = src_mount_ihp.lstrip(os.path.sep)
          dst_mount = dst_mount_ihp.lstrip(os.path.sep)
          mount_points.append((src_mount, dst_mount))
    return mount_points

  def _SetStorage(self, storage_name):
    """Sets the storage_object attribute.

    Args:
      storage_name (str): the name of the storage.
    Returns:
      BaseStorage: a storage object.
    Raises:
      BadContainerException: if no storage Driver is defined, or if it is not
        implemented
    """
    storage_class = self.STORAGES_MAP.get(storage_name, None)

    if storage_class is None:
      raise errors.BadContainerException(
          f'Storage driver {storage_name} is not implemented')

    self.storage_object = storage_class(
        self.docker_directory, self.docker_version)

  def Mount(self, mount_dir):
    """Mounts the specified container's filesystem.

    Args:
      mount_dir (str): the path to the destination mount point
    """
    commands = self.storage_object.MakeMountCommands(self, mount_dir)
    for c in commands:
      subprocess.call(c, shell=False)
