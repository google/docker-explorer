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

from __future__ import print_function, unicode_literals

import json
import os
import subprocess

from docker_explorer import errors
from docker_explorer import storage
from docker_explorer import utils

# Ugly Py2/Py3 compat code.
# Undo in 2020+
try:
  input = raw_input  # pylint: disable=redefined-builtin
except NameError:
  pass


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
        'Provided path is not a directory "{0}"'.format(docker_root_directory))
  containers_directory = os.path.join(docker_root_directory, 'containers')

  if not os.path.isdir(containers_directory):
    raise errors.BadStorageException(
        'Containers directory {0} does not exist'.format(containers_directory))
  container_ids_list = os.listdir(containers_directory)

  return container_ids_list


class Container(object):
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
    volumes (list(tuple)): list of mount points to bind from host to the
      container. (Docker storage backend v1).
  """

  STORAGES_MAP = {
      'aufs': storage.AufsStorage,
      'overlay': storage.OverlayStorage,
      'overlay2': storage.Overlay2Storage
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
          'Unable to find container configuration file {0:s}'.format(
              container_info_json_path)
      )
    with open(container_info_json_path) as container_info_json_file:
      container_info_dict = json.load(container_info_json_file)


    if container_info_dict is None:
      raise errors.BadContainerException(
          'Could not load container configuration file {0}'.format(
              container_info_json_path)
      )

    self.container_id = container_info_dict.get('ID', None)
    json_config = container_info_dict.get('Config', None)
    if json_config:
      self.config_image_name = json_config.get('Image', None)
      self.config_labels = json_config.get('Labels', None)
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
          '{0} container config file lacks Driver key'.format(
              container_info_json_path))

    self._SetStorage(self.storage_name)
    self.volumes = container_info_dict.get('Volumes', None)

    if self.docker_version == 2:
      c_path = os.path.join(
          self.docker_directory, 'image', self.storage_name, 'layerdb',
          'mounts', container_id)
      with open(os.path.join(c_path, 'mount-id')) as mount_id_file:
        self.mount_id = mount_id_file.read()

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
      size = int(open(path).read())
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
      with open(layer_info_path) as layer_info_file:
        return json.load(layer_info_file)

    return None

  def GetOrderedLayers(self):
    """Returns an array of the sorted layer IDs for a container.

    Returns:
      list (str): a list of layer IDs.
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
        with open(layer_info_path) as layer_info_file:
          layer_info = json.load(layer_info_file)
          current_layer = layer_info.get('parent', None)
      elif self.docker_version == 2:
        hash_method, layer_id = current_layer.split(':')
        parent_layer_path = os.path.join(
            self.docker_directory, 'image', self.storage_name, 'imagedb',
            'metadata', hash_method, layer_id, 'parent')
        if not os.path.isfile(parent_layer_path):
          break
        with open(parent_layer_path) as parent_layer_file:
          current_layer = parent_layer_file.read().strip()

    return layer_list

  def GetHistory(self, show_empty_layers=False):
    """Returns a dict containing the modification history of the container.

    Args:
      show_empty_layers (bool): whether to display empty layers.
    Returns:
      dict: object describing history of the container.
    """
    result_dict = {}
    for layer in self.GetOrderedLayers():
      layer_info = self.GetLayerInfo(layer)
      layer_dict = {}

      if layer is None:
        raise ValueError('Layer {0:s} does not exist'.format(layer))
      layer_size = self.GetLayerSize(layer)
      layer_dict['size'] = layer_size
      if layer_size > 0 or show_empty_layers or self.docker_version == 2:
        layer_dict['created_at'] = utils.FormatDatetime(layer_info['created'])
        container_cmd = layer_info['container_config'].get('Cmd', None)
        if container_cmd:
          layer_dict['container_cmd'] = ' '.join(container_cmd)
        comment = layer_info.get('comment', None)
        if comment:
          layer_dict['comment'] = comment
      result_dict[layer] = layer_dict

    return result_dict

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
          'Storage driver {0} is not implemented'.format(storage_name))

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
