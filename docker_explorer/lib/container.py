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

from docker_explorer import errors
from docker_explorer.lib import utils


class Container(object):
  """Implements methods to access information about a Docker container.

  Attributes:
    config_image_name (str): the name of the container's image (eg: 'busybox').
    config_labels (list(str)): labels attached to the container.
    container_id (str): the ID of the container.
    creation_timestamp (str): the container's creation timestamp.
    image_id (str): the ID of the container's image.
    mount_points (list(dict)): list of mount points to bind from host to the
      container. (Docker storage backend v2).
    name (str): the name of the container.
    running (boolean): True if the container is running.
    start_timestamp (str): the container's start timestamp.
    storage_driver (str): the container's storage driver.
    volumes (list(tuple)): list of mount points to bind from host to the
      container. (Docker storage backend v1).
  """

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
    self.storage_driver = container_info_dict.get('Driver', None)
    if self.storage_driver is None:
      raise errors.BadContainerException(
          '{0} container config file lacks Driver key'.format(
              container_info_json_path))
    self.volumes = container_info_dict.get('Volumes', None)

    if self.docker_version == 2:
      c_path = os.path.join(
          self.docker_directory, 'image', self.storage_driver, 'layerdb',
          'mounts', container_id)
      with open(os.path.join(c_path, 'mount-id')) as mount_id_file:
        self.mount_id = mount_id_file.read()

  def GetLayerSize(self, layer_id):
    """Returns the size of the layer.

    Args:
      layer_id (str): the layer id to get the size of.

    Returns:
      int: the size of the layer in bytes.
    """
    size = 0
    if self.docker_version == 1:
      path = os.path.join(self.docker_directory, 'graph',
                          layer_id, 'layersize')
      size = int(open(path).read())
    # TODO(romaing) Add docker storage v2 support
    return size

  def GetLayerInfo(self, layer_id):
    """Gets a docker FS layer information.

    Returns:
      dict: the container information.
    """
    if self.docker_version == 1:
      layer_info_path = os.path.join(
          self.docker_directory, 'graph', layer_id, 'json')
    elif self.docker_version == 2:
      hash_method, layer_id = layer_id.split(':')
      layer_info_path = os.path.join(
          self.docker_directory, 'image', self.storage_driver, 'imagedb',
          'content', hash_method, layer_id)
    layer_info = None
    if os.path.isfile(layer_info_path):
      with open(layer_info_path) as layer_info_file:
        layer_info = json.load(layer_info_file)
        return layer_info
    return None

  def GetOrderedLayers(self):
    """Returns an array of the sorted image ID for a container.

    Returns:
      list(str): a list of layer IDs (hashes).
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
            self.docker_directory, 'image', self.storage_driver, 'imagedb',
            'metadata', hash_method, layer_id, 'parent')
        if not os.path.isfile(parent_layer_path):
          break
        with open(parent_layer_path) as parent_layer_file:
          current_layer = parent_layer_file.read().strip()

    return layer_list

  def GetHistory(self, show_empty_layers=False):
    """Returns a string representing the modification history of the container.

    Args:
      show_empty_layers (bool): whether to display empty layers.
    Returns:
      str: the human readable history.
    """
    history_str = ''
    for layer in self.GetOrderedLayers():
      layer_info = self.GetLayerInfo(layer)
      if layer is None:
        raise ValueError('Layer {0:s} does not exist'.format(layer))
      history_str += '-------------------------------------------------------\n'
      history_str += layer+'\n'
      if layer_info is None:
        history_str += 'no info =('
      else:
        layer_size = self.GetLayerSize(layer)
        if layer_size > 0 or show_empty_layers or self.docker_version == 2:
          history_str += '\tsize : {0:d}'.format(layer_size)
          history_str += '\tcreated at : {0:s}'.format(
              utils.FormatDatetime(layer_info['created']))
          container_cmd = layer_info['container_config'].get('Cmd', None)
          if container_cmd:
            history_str += '\twith command : {0:s}'.format(
                ' '.join(container_cmd))
          comment = layer_info.get('comment', None)
          if comment:
            history_str += '\tcomment : {0:s}'.format(comment)
        else:
          history_str += 'Empty layer'
    return history_str
