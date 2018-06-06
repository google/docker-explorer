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
import codecs
import os
import sys

from docker_explorer import errors
from docker_explorer.lib import aufs
from docker_explorer.lib import overlay

# This is to fix UnicodeEncodeError issues when python
# suddenly changes the output encoding when sys.stdout is
# piped into something else.
sys.stdout = codecs.getwriter('utf8')(sys.stdout)


class DockerExplorer(object):
  """Main class for the DockerExplorer tool.

  Attributes:
    docker_directory (str): Path to use as the root of the Docker runtime.
      Default is '/var/lib/docker'.
    storage_object (lib.Storage): The object implementing the methods for
      exploring the Docker containers.
  """

  def __init__(self):
    """Initializes the ContainerInfo class."""
    self._argument_parser = None
    self.docker_directory = '/var/lib/docker'
    self.storage_object = None

  def DetectStorage(self):
    """Detects the storage backend.

    More info :
    https://docs.docker.com/engine/userguide/storagedriver/
    http://jpetazzo.github.io/assets/2015-06-04-deep-dive-into-docker-storage-drivers.html#60

    Raises:
      errors.BadStorageException: If the storage backend couldn't be detected.
    """
    if not os.path.isdir(self.docker_directory):
      err_message = (
          '{0:s} is not a Docker directory\n'
          'Please specify the Docker\'s directory path.\n'
          'hint: de.py -r /var/lib/docker').format(self.docker_directory)
      raise errors.BadStorageException(err_message)

    self.containers_directory = os.path.join(
        self.docker_directory, 'containers')

    if os.path.isfile(
        os.path.join(self.docker_directory, 'repositories-aufs')):
      # Handles Docker engine storage versions 1.9 and below.
      self.storage_object = aufs.AufsStorage(
          docker_directory=self.docker_directory, docker_version=1)
    elif os.path.isdir(os.path.join(self.docker_directory, 'overlay2')):
      self.storage_object = overlay.Overlay2Storage(
          docker_directory=self.docker_directory)
    elif os.path.isdir(os.path.join(self.docker_directory, 'overlay')):
      self.storage_object = overlay.OverlayStorage(
          docker_directory=self.docker_directory)
    elif os.path.isdir(os.path.join(self.docker_directory, 'aufs')):
      self.storage_object = aufs.AufsStorage(
          docker_directory=self.docker_directory)
    if self.storage_object is None:
      err_message = (
          'Could not detect storage system. '
          'Make sure the docker directory ({0:s}) is correct. '
          'If it is correct, you might want to run this script'
          ' with higher privileges.'.format(self.docker_directory))
      raise errors.BadStorageException(err_message)

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

    args:
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
    """Parses the command line options.

    Returns:
      Namespace: the populated namespace.
    """
<<<<<<< Updated upstream
=======
    container_ids_list = os.listdir(self.containers_directory)
    if not container_ids_list:
      print('Couldn\'t find any container configuration file (\'{0:s}\'). '
            'Make sure the docker repository ({1:s}) is correct. '
            'If it is correct, you might want to run this script'
            ' with higher privileges.').format(
                self.container_config_filename, self.docker_directory)
    return [self.GetContainer(cid) for cid in container_ids_list]

  def GetContainersList(self, only_running=False):
    """Returns a list of container ids which were running.
>>>>>>> Stashed changes

    self.docker_directory = os.path.abspath(options.docker_directory)

  def Mount(self, container_id, mountpoint):
    """Mounts the specified container's filesystem.

    Args:
      container_id (str): the ID of the container.
      mountpoint (str): the path to the destination mount point.
    """
<<<<<<< Updated upstream
    if self.storage_object is None:
      self.DetectStorage()
    self.storage_object.Mount(container_id, mountpoint)

=======
    container_object = self.GetContainer(container_id)
    self.storage_object.Mount(container_object, mountpoint)

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

>>>>>>> Stashed changes
  def ShowContainers(self, only_running=False):
    """Displays the running containers.

    Args:
      only_running (bool): Whether we display only running Containers.
    """
    if self.storage_object is None:
      self.DetectStorage()
    print(self.storage_object.ShowContainers(only_running=only_running))

  def ShowRepositories(self):
    """Displays information about the images in the Docker repository."""
    if self.storage_object is None:
      self.DetectStorage()
    print(self.storage_object.ShowRepositories())

  def ShowHistory(self, container_id, show_empty_layers=False):
    """Prints the modification history of a container.

    Args:
      container_id (str): the ID of the container.
      show_empty_layers (bool): whether to display empty layers.
    """
    if self.storage_object is None:
      self.DetectStorage()
    print(self.storage_object.GetHistory(container_id, show_empty_layers))

  def Main(self):
    """The main method for the DockerExplorer class.

    It instantiates the Storage Object and Handles arguments parsing.

    Raises:
      ValueError: If the arguments couldn't be parsed.
    """
    options = self.ParseArguments()
    self.ParseOptions(options)


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
        self.ShowRepositories()

    else:
      raise ValueError('Unhandled command %s' % options.command)


if __name__ == '__main__':
  DockerExplorer().Main()
