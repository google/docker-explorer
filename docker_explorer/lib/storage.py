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
"""Base class for a Docker Storage object."""


import json
import os
import subprocess
import sys

from docker_explorer.lib import container
from docker_explorer.lib import utils


class Storage(object):
  """This class provides tools to list and access containers metadata.

  Every method provided is agnostic of the implementation used (AuFS,
  btrfs, etc.).
  """

  def __init__(self, docker_directory='/var/lib/docker', docker_version=2):
    """Initialized a Storage object.

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

  def GetAllContainersInfo(self):
    """Gets a list containing information about all containers.

    Returns:
      list (dict): the list of Container objects.
    """
    container_ids_list = os.listdir(self.containers_directory)
    if not container_ids_list:
      print('Couldn\'t find any container configuration file (\'{0:s}\'). '
            'Make sure the docker repository ({1:s}) is correct. '
            'If it is correct, you might want to run this script'
            ' with higher privileges.').format(
                self.container_config_filename, self.docker_directory)
    container_info_list = [self.GetContainerInfo(x) for x in container_ids_list]

    return container_info_list

  def GetOrderedLayers(self, container_id):
    """Returns an array of the sorted image ID for a container ID.

    Args:
      container_id (str): the ID of the container.

    Returns:
      list(str): a list of layer IDs (hashes).
    """
    layer_list = []
    current_layer = container_id
    layer_path = os.path.join(self.docker_directory, 'graph', current_layer)
    if not os.path.isdir(layer_path):
      config_file_path = os.path.join(
          self.containers_directory, current_layer,
          self.container_config_filename)
      if not os.path.isfile(config_file_path):
        return []
      with open(config_file_path) as config_file:
        json_dict = json.load(config_file)
        current_layer = json_dict.get('Image', None)

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
            self.docker_directory, 'image', self.STORAGE_METHOD, 'imagedb',
            'metadata', hash_method, layer_id, 'parent')
        if not os.path.isfile(parent_layer_path):
          break
        with open(parent_layer_path) as parent_layer_file:
          current_layer = parent_layer_file.read().strip()

    return layer_list

  def GetContainerInfo(self, container_id):
    """Returns a dictionary containing the container_id setting.

    Args:
      container_id (str): the ID of the container.

    Returns:
      Container: the container's info.
    """
    container_info_json_path = os.path.join(
        self.containers_directory, container_id, self.container_config_filename)
    if os.path.isfile(container_info_json_path):
      container_info = container.Container(
          container_id, container_info_json_path)

    if self.docker_version == 2:
      c_path = os.path.join(
          self.docker_directory, 'image', self.STORAGE_METHOD, 'layerdb',
          'mounts', container_id)
      with open(os.path.join(c_path, 'mount-id')) as mount_id_file:
        container_info.mount_id = mount_id_file.read()

    return container_info

  def GetContainersList(self, only_running=False):
    """Returns a list of container ids which were running.

    Args:
      only_running (bool): Whether we return only running Containers.
    Returns:
      list(dict): list of Containers information objects.
    """
    containers_info_list = sorted(
        self.GetAllContainersInfo(), key=lambda x: x.start_timestamp)
    if only_running:
      containers_info_list = [x for x in containers_info_list if x.running]
    return containers_info_list

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
      s = rf.read()
    return result_string + utils.PrettyPrintJSON(s)

  def ShowContainers(self, only_running=False):
    """Returns a string describing the running containers.

    Args:
      only_running (bool): Whether we display only running Containers.
    Returns:
      str: the string displaying information about running containers.
    """
    result_string = ''
    for container_info in self.GetContainersList(only_running=only_running):
      image_id = container_info.image_id
      if self.docker_version == 2:
        image_id = image_id.split(':')[1]

      if container_info.config_labels:
        labels_list = ['{0:s}: {1:s}'.format(k, v) for (k, v) in
                       container_info.config_labels.items()]
        labels_str = ', '.join(labels_list)
        result_string += 'Container id: {0:s} / Labels : {1:s}\n'.format(
            container_info.container_id, labels_str)
      else:
        result_string += 'Container id: {0:s} / No Label\n'.format(
            container_info.container_id)
      result_string += '\tStart date: {0:s}\n'.format(
          utils.FormatDatetime(container_info.start_timestamp))
      result_string += '\tImage ID: {0:s}\n'.format(image_id)
      result_string += '\tImage Name: {0:s}\n'.format(
          container_info.config_image_name)

    return result_string

  def GetLayerSize(self, container_id):
    """Returns the size of the layer.

    Args:
      container_id (str): the id to get the size of.

    Returns:
      int: the size of the layer in bytes.
    """
    size = 0
    if self.docker_version == 1:
      path = os.path.join(self.docker_directory, 'graph',
                          container_id, 'layersize')
      size = int(open(path).read())
    # TODO(romaing) Add docker storage v2 support
    return size

  def GetLayerInfo(self, container_id):
    """Gets a docker FS layer information.

    Args:
      container_id (str): the container ID.

    Returns:
      dict: the container information.
    """
    if self.docker_version == 1:
      layer_info_path = os.path.join(
          self.docker_directory, 'graph', container_id, 'json')
    elif self.docker_version == 2:
      hash_method, container_id = container_id.split(':')
      layer_info_path = os.path.join(
          self.docker_directory, 'image', self.STORAGE_METHOD, 'imagedb',
          'content', hash_method, container_id)
    container_info = None
    if os.path.isfile(layer_info_path):
      with open(layer_info_path) as layer_info_file:
        container_info = json.load(layer_info_file)
        return container_info
    return None

  def _MakeExtraVolumeCommands(self, container_info, mount_dir):
    """Generates the shell command to mount external Volumes if present.

    Args:
      container_info (dict): the container's metadata.
      mount_dir (str): the destination mount_point.

    Returns:
      list(str): a list of extra commands, or the empty list if no volume is to
        be mounted.
    """
    extra_commands = []
    if self.docker_version == 1:
      # 'Volumes'
      container_volumes = container_info.volumes
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
      container_mount_points = container_info.mount_points
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

  def Mount(self, container_id, mount_dir):
    """Mounts the specified container's filesystem.

    Args:
      container_id (str): the ID of the container.
      mount_dir (str): the path to the destination mount point
    """

    commands = self.MakeMountCommands(container_id, mount_dir)
    for c in commands:
      print(c)
    print('Do you want to mount this container Id: {0:s} on {1:s} ?\n'
          '(ie: run these commands) [Y/n]').format(container_id, mount_dir)
    choice = raw_input().lower()
    if not choice or choice == 'y' or choice == 'yes':
      for c in commands:
        # TODO(romaing) this is quite unsafe, need to properly split args
        subprocess.call(c, shell=True)

  def GetHistory(self, container_id, show_empty_layers=False):
    """Returns a string representing the modification history of a container.

    Args:
      container_id (str): the ID of the container.
      show_empty_layers (bool): whether to display empty layers.
    Returns:
      str: the human readable history.
    """
    # TODO(romaing): Find a container_id from only the first few characters.
    history_str = ''
    for layer in self.GetOrderedLayers(container_id):
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
              utils.FormatDatetime(layer_info['created'])))
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
