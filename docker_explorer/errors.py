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
"""Custom exceptions."""

from __future__ import unicode_literals


class DockerExplorerError(Exception):
  """Base class for DockerExplorer custom errors."""

  def __init__(self, message):
    """Constructor for a DockerExplorerError.

    Args:
      message (str): the error message.
    """
    super().__init__(message)
    self.message = message


class BadContainerException(DockerExplorerError):
  """Raised when there was an issue parsing a Container configuration file."""


class BadStorageException(DockerExplorerError):
  """Raised when the Storage method detection failed."""


class DownloaderException(DockerExplorerError):
  """Raised when querying the Docker hub API failed."""

  def __init__(self, message):
    """Constructor for a DockerExplorerError.

    Args:
      message (str): the error message.
    """
    super().__init__(message)
    self.message = message
    self.http_code = None
    self.http_message = None
