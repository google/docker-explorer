"""Module for downloading information from Docker Hub registry"""

import logging
import re
import requests

logger = logging.getLogger('docker-explorer')


class DockerImageDownloader():
  """Helper class to download information for an image name (ie: 'busybox')."""

  BASE_API_URL = 'https://registry-1.docker.io/v2/'

  def __init__(self, image_name):
    """Initializes a DockerImageDownloader.

    Args:
      image_name(str): the input argument to select the image from the registry.
    """
    self._access_token = None
    self._manifest = None

    self.repository, self.tag = self._SetupRepository(image_name)

    self.repository_url = self.BASE_API_URL + '/' + self.repository

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

    repository = '{}/{}'.format(repository, image)
    tag = tag
    return (repository, tag)

  def _GetToken(self):
    """Requests an access token from Docker registry."""
    auth_url = ('https://auth.docker.io/token?service=registry.docker.io'
                '&scope=repository:{0:s}:pull'.format(self.repository))
    response = requests.get(auth_url)
    self._access_token = response.json().get('access_token', None)

  def _RegistryAPIGet(self, url):
    """Calls the Docker registry API.

    Args:
      url(str): the API method to call (ie: '/manifest/tag').
    Returns:
      requests.Response: the HTTP response, or None if the request failed.
    """
    if not self._access_token:
      self._GetToken()
    headers = {
        'Authorization':'Bearer '+ self._access_token,
        'Accept':'application/vnd.docker.distribution.manifest.v2+json'}
    response = requests.get(self.repository_url+url, headers=headers)
    if response.status_code != 200:
      return None
    return response

  def DownloadPseudoDockerfile(self):
    """Downloads a pseudo DockerFile for the image."""

    if not self._manifest:
      manifest = self._RegistryAPIGet('/manifests/' + self.tag).json()

    if manifest.get('config'):
      digest = manifest.get('config').get('digest')
      docker_configuration = self._RegistryAPIGet('/blobs/' + digest).json()
      with open('Dockerfile', 'w') as dockerfile:
        dockerfile.write(self.BuildDockerfileFromManifest(docker_configuration))
      logger.info('Downloaded Dockerfile')

  def DownloadLayers(self):
    """Downloads layers for the image."""

    if not self._manifest:
      manifest = self._RegistryAPIGet('/manifests/' + self.tag).json()

    for layer in manifest.get('layers', []):
      digest = layer.get('digest')
      response = self._RegistryAPIGet('/blobs/' + digest)
      layer_filename = '{0:s}.tgz'.format(digest.split(':')[1])
      with open(layer_filename, 'wb') as layer_blob:
        layer_blob.write(response.content)
      logger.info('Downloaded {0:s}'.format(layer_filename))

  def BuildDockerfileFromManifest(self, docker_configuration):
    """Generates a pseudo-Dockerfile from a parsed Docker configuration.

    Args:
      docker_configuration(dict): the Docker configuration manifest.

    Returns:
      str: the pseudo Dockerfile
    """

    docker_file_statements = ['Pseudo Dockerfile:', '']
    histories = [history['created_by'] for history in
                 sorted(docker_configuration['history'],
                        key=lambda l: l['created'])]

    for history in histories:
      m = re.search(r'ENTRYPOINT (.+)$', history)
      if m:
        docker_file_statements.append('ENTRYPOINT ' + m.group(1))
        continue

      m = re.search(r' ADD file:(.+) in (.+)$', history)
      if m:
        docker_file_statements.append(
            'ADD {0:s} {1:s}'.format(m.group(1), m.group(2)))
        continue

      m = re.search(r' CMD (.+)$', history)
      if m:
        docker_file_statements.append('CMD '+ m.group(1))
        continue

      m = re.search(r'^/bin/sh -c (.+)$', history)
      if m:
        docker_file_statements.append('RUN {0:s}'.format(m.group(1)))
        continue

      m = re.search(r'^/bin/sh -c (.+)$', history)
      if m:
        docker_file_statements.append('RUN {0:s}'.format(m.group(1)))
        continue

      docker_file_statements.append(history)
    return '\n'.join(docker_file_statements)
