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
"""Docker Explorer.

A tool to parse offline Docker installation.
"""

from __future__ import print_function, unicode_literals

import argparse
import os

from docker_explorer import errors
from docker_explorer.lib import container
from docker_explorer.lib import utils


class DockerExplorer(object):
  """Main class for the DockerExplorer tool.

  Attributes:
    docker_directory (str): Path to use as the root of the Docker runtime.
      Default is '/var/lib/docker'.
  """

  def __init__(self):
    """Initializes the ContainerInfo class."""
    self._argument_parser = None
    self.container_config_filename = 'config.v2.json'
    self.containers_directory = None
    self.docker_directory = None
    self.docker_version = 2

  def _SetDockerDirectory(self, docker_path):
    """Sets the Docker main directory.

    Args:
      docker_path(str): the absolute path to the docker directory.
    """
    self.docker_directory = docker_path
    if not os.path.isdir(self.docker_directory):
      msg = '{0:s} is not a Docker directory'.format(self.docker_directory)
      raise errors.BadStorageException(msg)

    self.containers_directory = os.path.join(
        self.docker_directory, 'containers')

  def AddBasicOptions(self, argument_parser):
    """Adds the global options to the argument_parser.

    Args:
      argument_parser (argparse.ArgumentParser):
        the argument parser to add the command to.
    """

    argument_parser.add_argument(
        '-r', '--docker-directory',
        help='Set the root docker directory. Default is /var/lib/docker',
        action='store', default='/var/lib/docker')

  def AddMountCommand(self, args):
    """Adds the mount command to the argument_parser.

    Args:
      args (argument_parser): the argument parser to add the command to.
    """
    mount_parser = args.add_parser(
        'mount',
        help=('Will generate the command to mount the AuFS at the '
              'corresponding container id'))
    mount_parser.add_argument(
        'container_id',
        help='The container id (can be the first few characters of the id)')
    mount_parser.add_argument('mountpoint', help='Where to mount')

  def AddListCommand(self, args):
    """Adds the list command to the argument_parser.

    Args:
      args (argparse.ArgumentParser): the argument parser to add the command to.
    """
    list_parser = args.add_parser('list', help='List stuff')
    list_parser.add_argument(
        'what', default='repos',
        help='Stuff to list', choices=[
            'repositories', 'running_containers', 'all_containers'])

  def AddHistoryCommand(self, args):
    """Adds the history command to the argument_parser.

    Args:
      args (argparse.ArgumentParser): the argument parser to add the command to.
    """
    history_parser = args.add_parser(
        'history',
        help='Shows an abridged history of changes for a container')
    history_parser.add_argument(
        'container_id',
        help='The container id (can be the first few characters of the id)')
    history_parser.add_argument(
        '--show-empty', help='Show empty layers (disabled by default)',
        action='store_true')

  def ParseArguments(self):
    """Parses the command line arguments.

    Returns:
      argparse.ArgumentParser : the argument parser object.
    """
    self._argument_parser = argparse.ArgumentParser()
    self.AddBasicOptions(self._argument_parser)

    command_parser = self._argument_parser.add_subparsers(dest='command')
    self.AddMountCommand(command_parser)
    self.AddListCommand(command_parser)
    self.AddHistoryCommand(command_parser)

    opts = self._argument_parser.parse_args()

    return opts

  def ParseOptions(self, options):
    """Parses the command line options."""
    self.docker_directory = os.path.abspath(options.docker_directory)

  def GetContainer(self, container_id):
    """Returns a Container object given a container_id.

    Args:
      container_id (str): the ID of the container.

    Returns:
      container.Container: the container object.
    """
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
    if not os.path.isdir(self.containers_directory):
      raise errors.BadStorageException(
          'Containers directory {0} does not exist'.format(
              self.containers_directory))
    container_ids_list = os.listdir(self.containers_directory)
    if not container_ids_list:
      print('Could not find container configuration files ({0:s}) in {1:s}.\n'
            'Make sure the docker directory ({2:s}) is correct.\n'
            'If it is correct, you might want to run this script'
            ' with higher privileges.'.format(
                self.container_config_filename, self.containers_directory,
                self.docker_directory))
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

  def Mount(self, container_id, mountpoint):
    """Mounts the specified container's filesystem.

    Args:
      container_id (str): the ID of the container.
      mountpoint (str): the path to the destination mount point.
    """
    container_object = self.GetContainer(container_id)
    container_object.Mount(mountpoint)

  def GetContainersString(self, only_running=False):
    """Returns a string describing the running containers.

    Args:
      only_running (bool): Whether we display only running Containers.

    Returns:
      str: the string displaying information about running containers.
    """
    result_string = ''
    for container_object in self.GetContainersList(only_running=only_running):
      image_id = container_object.image_id
      if self.docker_version == 2:
        image_id = image_id.split(':')[1]

      if container_object.config_labels:
        labels_list = ['{0:s}: {1:s}'.format(k, v) for (k, v) in
                       container_object.config_labels.items()]
        labels_str = ', '.join(labels_list)
        result_string += 'Container id: {0:s} / Labels : {1:s}\n'.format(
            container_object.container_id, labels_str)
      else:
        result_string += 'Container id: {0:s} / No Label\n'.format(
            container_object.container_id)
      result_string += '\tStart date: {0:s}\n'.format(
          utils.FormatDatetime(container_object.start_timestamp))
      result_string += '\tImage ID: {0:s}\n'.format(image_id)
      result_string += '\tImage Name: {0:s}\n'.format(
          container_object.config_image_name)

    return result_string

  def ShowContainers(self, only_running=False):
    """Displays the running containers.

    Args:
      only_running (bool): Whether we display only running Containers.
    """
    print(self.GetContainersString(only_running=only_running))

  def ShowHistory(self, container_id, show_empty_layers=False):
    """Prints the modification history of a container.

    Args:
      container_id (str): the ID of the container.
      show_empty_layers (bool): whether to display empty layers.
    """
    container_object = self.GetContainer(container_id)
    print(container_object.GetHistory(show_empty_layers))

  def GetRepositoriesString(self):
    """Returns information about images in the local Docker repositories.

    Returns:
      str: human readable list of images in local Docker repositories.

    Raises:
      errors.BadStorageException: If required files or directories are not found
        in the provided Docker directory.
    """
    result_string = ''
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

    for repositories_file_path in repositories:
      result_string += (
          'Listing repositories from file {0:s}\n'.format(
              repositories_file_path))
      with open(repositories_file_path) as rf:
        result_string += utils.PrettyPrintJSON(rf.read())

    return result_string

  def Main(self):
    """The main method for the DockerExplorer class.

    It instantiates the Storage Object and Handles arguments parsing.

    Raises:
      ValueError: If the arguments couldn't be parsed.
    """
    options = self.ParseArguments()
    self.ParseOptions(options)

    self._SetDockerDirectory(self.docker_directory)

    if options.command == 'mount':
      self.Mount(options.container_id, options.mountpoint)

    elif options.command == 'history':
      self.ShowHistory(
          options.container_id, show_empty_layers=options.show_empty)

    elif options.command == 'list':
      if options.what == 'all_containers':
        self.ShowContainers()
      elif options.what == 'running_containers':
        self.ShowContainers(only_running=True)
      elif options.what == 'repositories':
        print(self.GetRepositoriesString())

    else:
      raise ValueError('Unhandled command %s' % options.command)


if __name__ == '__main__':
  try:
    DockerExplorer().Main()
  except errors.BadStorageException as exc:
    print('ERROR: {0}\n'.format(exc.message))
    print('Please specify a proper Docker directory path.\n'
          '	hint: de.py -r /var/lib/docker')
