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

from docker_explorer.lib import aufs
from docker_explorer.lib import overlay

# This is to fix UnicodeEncodeError issues when python
# suddenly changes the output encoding when sys.stdout is
# piped into something else.
sys.stdout = codecs.getwriter('utf8')(sys.stdout)


class BadStorageException(Exception):
  """Raised when the Storage method detection failed."""

  def __init__(self, message):
    self.message = message


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
    """Detects the storage backend. Only AuFS is currently supported.

    More info :
    https://docs.docker.com/engine/userguide/storagedriver/
    http://jpetazzo.github.io/assets/2015-06-04-deep-dive-into-docker-storage-drivers.html#60

    Returns:
      Storage: a Storage object.

    Raises:
      BadStorageException: If the storage backend couldn't be detected.
    """
    if not os.path.isdir(self.docker_directory):
      error_msg = (
          '{0:s} is not a Docker directory\n'
          'Please specify the Docker\'s directory path.\n'
          'hint: python {1:s} -r /var/lib/docker').format(
              self.docker_directory, sys.argv[0])
      raise BadStorageException(error_msg)

    if os.path.isfile(
        os.path.join(self.docker_directory, 'repositories-aufs')):
      # Handles Docker engine storage versions 1.9 and below.
      return aufs.AufsStorage(
          docker_directory=self.docker_directory, docker_version=1)
    elif os.path.isdir(os.path.join(self.docker_directory, u'overlay2')):
      return overlay.Overlay2Storage(docker_directory=self.docker_directory)
    elif os.path.isdir(os.path.join(self.docker_directory, 'overlay')):
      return overlay.OverlayStorage(docker_directory=self.docker_directory)
    elif os.path.isdir(os.path.join(self.docker_directory, 'aufs')):
      return aufs.AufsStorage(docker_directory=self.docker_directory)
    return None

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

    self.docker_directory = os.path.abspath(options.docker_directory)

  def Main(self):
    """The main method for the DockerExplorer class.

    It instantiates the Storage Object and Handles arguments parsing.

    Raises:
      ValueError: If the arguments couldn't be parsed.
    """
    options = self.ParseArguments()
    self.ParseOptions(options)

    self.storage_object = self.DetectStorage()
    if self.storage_object is None:
      print('Could not detect storage system. '
            'Make sure the docker directory ({0:s}) is correct. '
            'If it is correct, you might want to run this script'
            ' with higher privileges.').format(self.docker_directory)
      sys.exit(1)

    if options.command == 'mount':
      self.storage_object.Mount(options.container_id, options.mountpoint)

    elif options.command == 'history':
      self.storage_object.ShowHistory(
          options.container_id,
          show_empty_layers=options.show_empty)

    elif options.command == 'list':
      if options.what == 'all_containers':
        print(self.storage_object.ShowContainers())
      elif options.what == 'running_containers':
        print(self.storage_object.ShowContainers(only_running=True))
      elif options.what == 'repositories':
        print(self.storage_object.ShowRepositories())

    else:
      raise ValueError('Unhandled command %s' % options.command)


if __name__ == '__main__':
  DockerExplorer().Main()
