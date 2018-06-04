"""TODO(romaing): DO NOT SUBMIT without one-line documentation for container.

TODO(romaing): DO NOT SUBMIT without a detailed description of container.
"""

from __future__ import print_function, unicode_literals

import json


class Container(object):
  """Implements methods to access information about a Docker container.

  Attributes:
    config_image_name (str): the name of the container's image (eg: 'busybox').
    config_labels (list(str)): labels attached to the container.
    container_id (str): the ID of the container.
    creation_timestamp (str): the container's creation timestamp.
    image_id (str): the ID of the container's image.
    mount_points (list(dict)): list of mount points to bind from host to the
      container. (Docker storage backend v2).
    name (str): the name of the container.
    running (boolean): True if the container is running.
    start_timestamp (str): the container's start timestamp.
    storage_driver (str): the container's storage driver.
    volumes (list(tuple)): list of mount points to bind from host to the
      container. (Docker storage backend v1).
  """

  def __init__(self, container_id, container_info_json_path):
    """Initializes the Container class.

    Args:
      container_id (str): the container ID.
      container_info_json_path (str): the path to the JSON file containing the
        container's information.
    """
    self.container_id = container_id

    with open(container_info_json_path) as container_info_json_file:
      container_info_dict = json.load(container_info_json_file)

    json_config = container_info_dict.get('Config', None)
    if json_config:
      self.config_image_name = json_config.get('Image', None)
      self.config_labels = json_config.get('Labels', None)
    self.creation_timestamp = container_info_dict.get('Created', None)
    self.image_id = container_info_dict.get('Image', None)
    self.mount_points = container_info_dict.get('MountPoints', None)
    self.name = container_info_dict.get('Name', '')
    json_state = container_info_dict.get('State', None)
    if json_state:
      self.running = json_state.get('Running', False)
      self.start_timestamp = json_state.get('StartedAt', False)
    self.storage_driver = json_config.get('Driver', None)
    self.volumes = container_info_dict.get('Volumes', None)

    self.mount_id = None
