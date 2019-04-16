#!/usr/bin/python
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
"""Module for the Explorer object."""

import json
import os

from docker_explorer import container
from docker_explorer import errors
from docker_explorer import utils


class Explorer(object):
  """Class for a DockerExplorer object."""

  DEFAULT_DOCKER_DIRECTORY = '/var/lib/docker'
  DEFAULT_DOCKER_VERSION = 2

  def __init__(self):
    """Initializes the DockerExplorer class."""
    self.containers_directory = None
    self.docker_directory = self.DEFAULT_DOCKER_DIRECTORY
    self.docker_version = self.DEFAULT_DOCKER_VERSION

  def SetDockerDirectory(self, docker_path):
    """Sets the Docker main directory.

    Args:
      docker_path(str): the absolute path to the docker directory.
    Raises:
      errors.BadStorageException: if the path doesn't point to a Docker
        directory.
    """
    self.docker_directory = docker_path
    if not os.path.isdir(self.docker_directory):
      msg = '{0:s} is not a Docker directory'.format(self.docker_directory)
      raise errors.BadStorageException(msg)

    self.containers_directory = os.path.join(
        self.docker_directory, 'containers')

  def DetectDockerStorageVersion(self):
    """Detects Docker storage version (v1 or v2).

    Raises:
      errors.BadStorageException: when we couldn't detect the Docker storage
        version.
    """
    if not os.path.isdir(self.containers_directory):
      raise errors.BadStorageException(
          'Containers directory {0} does not exist.'.format(
              self.containers_directory))
    container_ids_list = os.listdir(self.containers_directory)
    if not container_ids_list:
      print('Could not find container directoried in {0:s}.\n'
            'Make sure the docker directory ({1:s}) is correct.\n'
            'If it is correct, you might want to run this script'
            ' with higher privileges.'.format(
                self.containers_directory, self.docker_directory))
    path_to_a_container = os.path.join(
        self.containers_directory, container_ids_list[0])
    if os.path.isfile(os.path.join(path_to_a_container, 'config.v2.json')):
      self.docker_version = 2
    elif os.path.isfile(os.path.join(path_to_a_container, 'config.json')):
      self.docker_version = 1
    else:
      raise errors.BadStorageException(
          'Could not find any container configuration file:\n'
          'Neither config.json nor config.v2.json found in {0:s}'.format(
              path_to_a_container)
      )

  def _GetFullContainerID(self, short_id):
    """Searches for a container ID from its first characters.

    Args:
      short_id (str): the first few characters of a container ID.
    Returns:
      str: the full container ID
    Raises:
      errors.DockerExplorerError: when we couldn't map the short version to
        exactly one full container ID.
    """
    if len(short_id) == 64:
      return short_id

    containers_dir = os.path.join(self.docker_directory, 'containers')
    possible_cids = []
    for container_dirs in sorted(os.listdir(containers_dir)):
      possible_cid = os.path.basename(container_dirs)
      if possible_cid.startswith(short_id):
        possible_cids.append(possible_cid)

    possible_cids_len = len(possible_cids)
    if possible_cids_len == 0:
      raise errors.DockerExplorerError(
          'Could not find any container ID starting with "{0}"'.format(
              short_id))
    if possible_cids_len > 1:
      raise errors.DockerExplorerError(
          'Too many container IDs starting with "{0}": {1}'.format(
              short_id, ', '.join(possible_cids)))

    return possible_cids[0]

  def GetContainer(self, container_id_part):
    """Returns a Container object given the first characters of a container_id.

    Args:
      container_id_part (str): the first characters of a container ID.

    Returns:
      container.Container: the container object.
    """
    container_id = self._GetFullContainerID(container_id_part)
    return container.Container(
        self.docker_directory, container_id, docker_version=self.docker_version)

  def GetAllContainers(self):
    """Gets a list containing information about all containers.

    Returns:
      list(Container): the list of Container objects.

    Raises:
      errors.BadStorageException: If required files or directories are not found
        in the provided Docker directory.
    """
    container_ids_list = container.GetAllContainersIDs(self.docker_directory)
    if not container_ids_list:
      print('Could not find container directory in {0:s}.\n'
            'Make sure the docker directory ({1:s}) is correct.\n'
            'If it is correct, you might want to run this script'
            ' with higher privileges.'.format(
                self.containers_directory, self.docker_directory))
    return [self.GetContainer(cid) for cid in container_ids_list]

  def GetContainersList(self, only_running=False):
    """Returns a list of Container objects, sorted by start time.

    Args:
      only_running (bool): Whether we return only running Containers.

    Returns:
      list(Container): list of Containers information objects.
    """
    containers_list = sorted(
        self.GetAllContainers(), key=lambda x: x.start_timestamp)
    if only_running:
      containers_list = [x for x in containers_list if x.running]
    return containers_list

  def GetContainersJson(self, only_running=False):
    """Returns a dict describing the running containers.

    Args:
      only_running (bool): Whether we display only running Containers.

    Returns:
      dict: A dict object representing the containers.
    """
    result = []
    for container_object in self.GetContainersList(only_running=only_running):
      image_id = container_object.image_id
      if self.docker_version == 2:
        image_id = image_id.split(':')[1]
      container_json = {
          'container_id': container_object.container_id,
          'image_id': image_id
      }

      if container_object.config_labels:
        container_json['labels'] = container_object.config_labels
      container_json['start_date'] = utils.FormatDatetime(
          container_object.start_timestamp)
      container_json['image_name'] = container_object.config_image_name

      if container_object.mount_id:
        container_json['mount_id'] = container_object.mount_id

      result.append(container_json)

    return result

  def GetRepositoriesString(self):
    """Returns information about images in the local Docker repositories.

    Returns:
      str: human readable list of images in local Docker repositories.

    Raises:
      errors.BadStorageException: If required files or directories are not found
        in the provided Docker directory.
    """
    repositories = []
    if self.docker_version == 1:
      repositories = [os.path.join(self.docker_directory, 'repositories-aufs')]
    else:
      image_path = os.path.join(self.docker_directory, 'image')
      if not os.path.isdir(image_path):
        raise errors.BadStorageException(
            'Expected image directory {0} does not exist.'.format(image_path))
      for storage_method in os.listdir(image_path):
        repositories_file_path = os.path.join(
            image_path, storage_method, 'repositories.json')
        if os.path.isfile(repositories_file_path):
          repositories.append(repositories_file_path)

    result = []
    for repositories_file_path in sorted(repositories):
      with open(repositories_file_path) as rf:
        repo_obj = json.loads(rf.read())
        repo_obj['path'] = repositories_file_path
        result.append(repo_obj)

    return utils.PrettyPrintJSON(result)
