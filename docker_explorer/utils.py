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
"""Module to provide some helper methods."""

from __future__ import unicode_literals

import datetime
import json


def FormatDatetime(timestamp):
  """Formats a Docker timestamp.

  Args:
    timestamp (str): the Docker timestamp.

  Returns:
    str: Human readable timestamp.
  """
  try:
    time = datetime.datetime.fromisoformat(timestamp)
  except AttributeError:
    # datetime.fromisoformat() is only present in python >= 3.6
    timestamp = timestamp[:26]
    time = datetime.datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%S.%f')
  except ValueError:
    # Strip non-ISO compliant precision and time zone designator.
    timestamp = timestamp[:26]
    if timestamp[-1].isalpha():
      timestamp = timestamp[:-1]
    time = datetime.datetime.fromisoformat(timestamp)
  return time.isoformat()


def PrettyPrintJSON(dict_object, sort_keys=True):
  """Generates a easy to read representation of a dict object.

  Args:
    dict_object (dict): dict to convert to string
    sort_keys (bool): bool to enable key sorting

  Returns:
    str: pretty printed JSON string.
  """
  pretty_json = json.dumps(
      dict_object, sort_keys=sort_keys, indent=4, separators=(', ', ': '))
  return pretty_json + '\n'
