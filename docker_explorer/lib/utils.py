"""TODO(romaing): DO NOT SUBMIT without one-line documentation for utils.

TODO(romaing): DO NOT SUBMIT without a detailed description of utils.
"""

from __future__ import print_function, unicode_literals

from datetime import datetime
import json


def FormatDatetime(timestamp):
  """Formats a Docker timestamp.

  Args:
    timestamp (str): the Docker timestamp.

  Returns:
    str: Human readable timestamp.
  """
  try:
    time = datetime.strptime(timestamp[0:26], '%Y-%m-%dT%H:%M:%S.%f')
  except ValueError:
    time = datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%SZ')
  return time.isoformat()

def PrettyPrintJSON(string):
  """Generates a easy to read representation of a JSON string.

  Args:
    string (str): JSON string.

  Returns:
    str: pretty printed JSON string.
  """
  return json.dumps(
      json.loads(string), sort_keys=True, indent=4, separators=(', ', ': '))

