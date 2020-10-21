#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright 2020 Google Inc.
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
"""Merge VHDX.

A tool to merge differencing VHDX files.
"""

import argparse
import sys

from docker_explorer import vhdx


class MergeVHDXTool:
  """Main class for the MergeVHDXTool tool."""

  def __init__(self):
    """Initializes the MergeVHDXTool class."""
    self._argument_parser = None

  def AddBasicOptions(self, argument_parser):
    """Adds the global options to the argument_parser.

    Args:
      argument_parser (argparse.ArgumentParser):
        the argument parser to add the command to.
    """
    argument_parser.add_argument(
      '-p', '--parent_disk', dest='parent_disk_name', action='store',
      required=True, help='The parent disk to be merged.')
    argument_parser.add_argument(
      '-c', '--child_disk', dest='child_disk_name', action='store',
      required=True, help='The child disk to be merged.')
    argument_parser.add_argument(
      '-o', '--out_image', dest='out_image_name', action='store',
      required=True, help='The output image name.')

  def ParseArguments(self):
    """Parses the command line arguments.

    Returns:
      argparse.ArgumentParser : the argument parser object.
    """
    self._argument_parser = argparse.ArgumentParser()
    self.AddBasicOptions(self._argument_parser)

    opts = self._argument_parser.parse_args()

    return opts

  def Main(self):
    """The main method for the MergeVHDXTool class.

    It handles arguments parsing and initiates the disk merge.
    """
    options = self.ParseArguments()

    parent_disk = vhdx.VHDXDisk(options.parent_disk_name)
    child_disk = vhdx.VHDXDisk(options.child_disk_name, parent_disk)
    out_image_fd = open(options.out_image_name, 'wb')

    print('This command will create a new disk image in the current'
        ' directory of size {0:d}GiB\nPlease confirm (y/n): '.format(
            child_disk.virtual_disk_size//1024**3), end='')
    confirm = input()
    if confirm.lower() != 'y':
      sys.exit()

    for block in range(0, child_disk.data_block_count):
      out_image_fd.write(child_disk.GetDataBlock(block))
    out_image_fd.close()


if __name__ == '__main__':
  MergeVHDXTool().Main()
