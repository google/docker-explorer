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
      errors.BadContainerException: if there was an error with parsing
        container_info_json_path
    """
    self.container_config_filename = 'config.v2.json'
    if docker_version == 1:
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
      raise errors.BadContainerException('TODO')
    self.volumes = container_info_dict.get('Volumes', None)

    if docker_version == 2:
      c_path = os.path.join(
          self.docker_directory, 'image', self.storage_driver, 'layerdb',
          'mounts', container_id)
      with open(os.path.join(c_path, 'mount-id')) as mount_id_file:
        self.mount_id = mount_id_file.read()

