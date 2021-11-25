"""Module for downloading information from Docker Hub registry."""

import logging
import os
import re
import requests

from docker_explorer import __version__ as de_version
from docker_explorer import errors

logger = logging.getLogger('docker-explorer')


class DockerImageDownloader:
  """Helper class to download information for an image name (ie: 'busybox')."""

  BASE_API_URL = 'https://registry-1.docker.io/v2/'

  def __init__(self, image_name, output_directory=None):
    """Initializes a DockerImageDownloader.

    Args:
      image_name(str): the input argument to select the image from the registry.
      output_directory(str): the option destination directory for downloads.
    """
    self._access_token = None
    self._manifest = None
    self._output_directory = output_directory

    self.image_name = image_name
    self.repository = None
    self.repository_url = None
    self.tag = None

  def _SetupRepository(self, image_name):
    """Sets the proper repository name and tag from an image_name input.

    Args:
      image_name(str): the input argument.
    """
    repo_and_image = image_name
    tag = 'latest'
    repository = 'library'

    if ':' in repo_and_image:
      repo_and_image, tag = repo_and_image.split(':')
    else:
      tag = 'latest'

    image = None
    if '/' in repo_and_image:
      repository, image = repo_and_image.split('/')
    else:
      image = repo_and_image

    if not self._output_directory:
      self._output_directory = os.path.join(repository, image, tag)
      os.makedirs(self._output_directory, exist_ok=True)

    repository = f'{repository}/{image}'

    self.repository = repository
    self.tag = tag
    self.repository_url = self.BASE_API_URL + '/' + self.repository

  def _GetToken(self):
    """Requests an access token from Docker registry."""
    if not self.repository:
      self._SetupRepository(self.image_name)
    auth_url = (
        'https://auth.docker.io/token?service=registry.docker.io'
        f'&scope=repository:{self.repository}:pull')
    response = requests.get(auth_url)
    self._access_token = response.json().get('access_token', None)

  def _RegistryAPIGet(self, url):
    """Calls the Docker registry API.

    Args:
      url(str): the API method to call (ie: '/manifest/tag').
    Returns:
      requests.Response: the HTTP response, or None if the request failed.
    Raises:
      errors.DownloaderException: when querying the DockerHub API errors out.
    """
    if not self.repository_url:
      self._SetupRepository(self.image_name)
    if not self._access_token:
      self._GetToken()
    headers = {
        'Authorization':'Bearer '+ self._access_token,
        'Accept':'application/vnd.docker.distribution.manifest.v2+json'}
    response = requests.get(self.repository_url+url, headers=headers)
    if response.status_code != 200:
      api_error = errors.DownloaderException(
          f'Error querying Docker Hub API: "{self.repository_url+url}"')
      api_error.http_code = response.status_code
      api_error.http_message = response.content
      raise api_error
    return response

  def _GetManifest(self):
    """Downloads a Manifest from Docker Hub API.

    Returns:
      dict: the manifest for the image.

    Raises:
      errors.DownloaderException: if there was an error fetching the manifest.
    """
    if not self.tag:
      self._SetupRepository(self.image_name)
    if not self._manifest:
      try:
        self._manifest = self._RegistryAPIGet('/manifests/' + self.tag).json()
      except errors.DownloaderException as e:
        container = f'{self.repository}:{self.tag}'
        logger.error(f'Error getting manifest for {container}')
        raise e
    return self._manifest

  def DownloadPseudoDockerfile(self):
    """Downloads a pseudo DockerFile for the image."""

    if self._GetManifest().get('config'):
      digest = self._manifest.get('config').get('digest')
      docker_configuration = self._RegistryAPIGet('/blobs/' + digest).json()
      docker_filepath = os.path.join(self._output_directory, 'Dockerfile')
      with open(docker_filepath, 'w', encoding='utf-8') as dockerfile:
        dockerfile.write(self.BuildDockerfileFromManifest(docker_configuration))
      logger.info('Downloaded Dockerfile to {self._output_directory}')

  def DownloadLayers(self):
    """Downloads layers for the image."""

    for layer in self._GetManifest().get('layers', []):
      digest = layer.get('digest')
      response = self._RegistryAPIGet('/blobs/' + digest)
      hash_digest = digest.split(':')[1]
      layer_filename = f'{hash_digest}.tgz'
      layer_path = os.path.join(self._output_directory, layer_filename)
      with open(layer_path, 'wb') as layer_blob:
        layer_blob.write(response.content)
      logger.info(f'Downloaded {layer_filename} to {self._output_directory}')

  def BuildDockerfileFromManifest(self, docker_configuration):
    """Generates a pseudo-Dockerfile from a parsed Docker configuration.

    Args:
      docker_configuration(dict): the Docker configuration manifest.

    Returns:
      str: the pseudo Dockerfile
    """

    docker_file_statements = [
        '# Pseudo Dockerfile',
        f'# Generated by de.py ({de_version})',
        '']
    histories = [history['created_by'] for history in
                 sorted(docker_configuration['history'],
                        key=lambda l: l['created'])]

    for history in histories:
      m = re.search(r'ENTRYPOINT (.+)$', history)
      if m:
        docker_file_statements.append('ENTRYPOINT ' + m.group(1))
        continue

      m = re.search(r'COPY (.+)$', history)
      if m:
        docker_file_statements.append('COPY ' + m.group(1))
        continue

      m = re.search(r' ADD file:(.+) in (.+)$', history)
      if m:
        docker_file_statements.append(f'ADD {m.group(1)} {m.group(2)}')
        continue

      m = re.search(r' CMD (.+)$', history)
      if m:
        docker_file_statements.append(f'CMD {m.group(1)}')
        continue

      m = re.search(r'^/bin/sh -c (.+)$', history)
      if m:
        docker_file_statements.append(f'RUN {m.group(1)}')
        continue

      m = re.search(r'^/bin/sh -c (.+)$', history)
      if m:
        docker_file_statements.append(f'RUN {m.group(1)}')
        continue

      docker_file_statements.append(history)
    return '\n'.join(docker_file_statements)
