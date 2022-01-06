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

from __future__ import unicode_literals

import argparse
import logging

import docker_explorer

from docker_explorer import downloader
from docker_explorer import errors
from docker_explorer import explorer
from docker_explorer import utils

logger = logging.getLogger('docker-explorer')


class DockerExplorerTool:
  """Main class for the DockerExplorerTool tool."""

  def __init__(self):
    """Initializes the DockerExplorerTool class."""
    self._argument_parser = None
    self._explorer = None
    self._filter_repositories = []

  def AddBasicOptions(self, argument_parser):
    """Adds the global options to the argument_parser.

    Args:
      argument_parser(argparse.ArgumentParser): the argument parser to add the
        command to.
    """
    version_string = f'docker-explorer - version {docker_explorer.__version__}'

    argument_parser.add_argument(
        '-d', '--debug', dest='debug', action='store_true', default=False,
        help='Enable debug messages.')

    argument_parser.add_argument(
        '-r', '--docker-directory',
        help=(
            'Set the root docker directory. '
            f'Default is {docker_explorer.DEFAULT_DOCKER_DIRECTORY}'),
        action='store', default=docker_explorer.DEFAULT_DOCKER_DIRECTORY)

    argument_parser.add_argument(
        '-V', '--version', dest='version', action='version',
        version=version_string, help='Show the version information.')

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

  def AddDownloadCommand(self, args):
    """Adds the download command to the argument_parser.

    Args:
      args (argument_parser): the argument parser to add the command to.
    """
    download_parser = args.add_parser(
        'download',
        help=('Downloads information from Docker Hub Registry base on an image'
              'name.'))
    download_parser.add_argument(
        'what', help='What to download', choices=[
            'all', 'dockerfile', 'layers'])
    download_parser.add_argument(
        'image_name',
        help='the image to download artifacts of (ie: \'busybox\')')

  def AddListCommand(self, args):
    """Adds the list command to the argument_parser.

    Args:
      args (argparse.ArgumentParser): the argument parser to add the command to.
    """
    list_parser = args.add_parser('list', help='List stuff')
    list_parser.add_argument(
        'what', default='all_containers',
        help='Stuff to list', choices=[
            'repositories', 'running_containers', 'all_containers'])
    list_parser.add_argument(
        '-F', '--filter_repositories', type=str, default='', help=(
            'Filter out containers running images from certain repositories. '
            'Ex: -F k8s.gcr.io,gke.gcr.io'))

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
      argparse.ArgumentParser: the argument parser object.
    """
    self._argument_parser = argparse.ArgumentParser()
    self.AddBasicOptions(self._argument_parser)

    command_parser = self._argument_parser.add_subparsers(dest='command')
    self.AddDownloadCommand(command_parser)
    self.AddMountCommand(command_parser)
    self.AddListCommand(command_parser)
    self.AddHistoryCommand(command_parser)

    opts = self._argument_parser.parse_args()

    if opts.command == 'list':
      if opts.filter_repositories:
        self._filter_repositories = [
            repo for repo in opts.filter_repositories.split(',') if repo]

    return opts

  def Mount(self, container_id, mountpoint):
    """Mounts the specified container's filesystem.

    Args:
      container_id (str): the ID of the container.
      mountpoint (str): the path to the destination mount point.
    """
    container_object = self._explorer.GetContainer(container_id)
    if container_object.storage_name == 'windowsfilter':
      print('Warning: Due to differences in the Windows container '
          'implementation this\ncommand will not actually mount the given '
          'container FS but will create a\nmountable raw image:\n\n '
          f'{container_object.mount_id}.raw\n\n'
          'Which can then be mounted using standard tools.')
    container_object.Mount(mountpoint)

  def ShowContainers(self, only_running=False):
    """Displays the running containers.

    Args:
      only_running (bool): Whether we display only running Containers.
    """
    print(utils.PrettyPrintJSON(
        self._explorer.GetContainersJson(
            only_running=only_running,
            filter_repositories=self._filter_repositories),
        sort_keys=False))

  def ShowHistory(self, container_id, show_empty_layers=False):
    """Prints the modification history of a container.

    Args:
      container_id (str): the ID of the container.
      show_empty_layers (bool): whether to display empty layers.
    """
    container_object = self._explorer.GetContainer(container_id)
    print(utils.PrettyPrintJSON(container_object.GetHistory(show_empty_layers),
                                sort_keys=False))

  def _SetLogging(self, debug):
    """Configures the logging module.

    Args:
      debug(bool): whether to show debug messages.
    """
    handler = logging.StreamHandler()
    logger.setLevel(logging.INFO)

    if debug:
      level = logging.DEBUG
      logger.setLevel(level)
      handler.setLevel(level)

    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] (%(processName)-10s) PID:%(process)d '
        '<%(module)s> %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

  def Main(self):
    """The main method for the DockerExplorerTool class.

    It instantiates the Storage Object and Handles arguments parsing.

    Raises:
      ValueError: If the arguments couldn't be parsed.
    """
    options = self.ParseArguments()

    self._SetLogging(debug=options.debug)

    self._explorer = explorer.Explorer()

    if options.command == 'download':
      try:
        dl = downloader.DockerImageDownloader(options.image_name)
        if options.what == 'all':
          dl.DownloadPseudoDockerfile()
          dl.DownloadLayers()
        if options.what == 'dockerfile':
          dl.DownloadPseudoDockerfile()
        if options.what == 'layers':
          dl.DownloadLayers()
      except errors.DownloaderException as exc:
        logger.debug(exc.message)
        logger.debug(exc.http_message)
        logger.error(
            f'Make sure the image \'{dl.repository}:{dl.tag}\' exists in the '
            'public Docker Hub registry: '
            f'https://hub.docker.com/r/{dl.repository}/tags')
      return

    self._explorer.SetDockerDirectory(options.docker_directory)
    self._explorer.DetectDockerStorageVersion()

    if not options.command:
      self.ShowContainers()

    elif options.command == 'mount':
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
        print(self._explorer.GetRepositoriesString())
    else:
      raise ValueError(f'Unhandled command {options.command}')


if __name__ == '__main__':
  try:
    DockerExplorerTool().Main()
  except errors.BadStorageException as main_exc:
    logger.debug(main_exc.message)
    logger.error('Please specify a proper Docker directory path.\n'
                 '	hint: de.py -r /var/lib/docker')
