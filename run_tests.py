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
"""Tests for the de.py tool."""

from __future__ import unicode_literals

import json
import os
import shutil
import sys
import tarfile
import unittest
import de

from lib import aufs
from lib import overlay
from lib import storage


# pylint: disable=missing-docstring
# pylint: disable=protected-access

class StorageTests(unittest.TestCase):
  """Tests methods in Storage class."""

  def testFormatDatetime(self):
    test_date = '2017-12-25T15:59:59.102938 msqedigrb msg'
    expected_time_str = '2017-12-25T15:59:59.102938'
    test_storage_object = storage.Storage()
    self.assertEqual(expected_time_str,
                     test_storage_object._FormatDatetime(test_date))


class AufsStorageTests(unittest.TestCase):
  """Tests helper methods in de.py."""

  def testPrettyPrintJSON(self):
    test_storage_object = aufs.AufsStorage()
    test_dict = {'test': [{'dict1': {'key1': 'val1'}, 'dict2': None}]}
    test_json = json.dumps(test_dict)
    expected_string = ('{\n    "test": [\n        {\n            "dict1": {\n'
                       '                "key1": "val1"\n            }, \n'
                       '            "dict2": null\n        }\n    ]\n}')
    self.assertEqual(expected_string,
                     test_storage_object._PrettyPrintJSON(test_json))


class TestDEMain(unittest.TestCase):
  """Tests DockerExplorer object methods."""

  def testParseArguments(self):
    de_test_object = de.DockerExplorer()

    prog = sys.argv[0]

    expected_docker_root = os.path.join('test_data', 'docker')

    args = [prog, '-r', expected_docker_root, 'list', 'repositories']
    sys.argv = args

    options = de_test_object.ParseArguments()
    usage_string = de_test_object._argument_parser.format_usage()
    expected_usage = (
        'usage: {0} [-h] [-r DOCKER_DIRECTORY] '
        '{{mount,list,history}} ...\n'.format(os.path.basename(__file__)))
    self.assertEqual(expected_usage, usage_string)

    de_test_object.ParseOptions(options)
    self.assertEqual(expected_docker_root, options.docker_directory)


class TestAufsStorage(unittest.TestCase):
  """Tests methods in the Storage object."""

  @classmethod
  def setUpClass(cls):
    docker_directory_path = os.path.join('test_data', 'docker')
    if not os.path.isdir(docker_directory_path):
      docker_tar = os.path.join('test_data', 'aufs.tgz')
      tar = tarfile.open(docker_tar, 'r:gz')
      tar.extractall('test_data')
      tar.close()

    de_test_object = de.DockerExplorer()
    de_test_object.docker_directory = docker_directory_path
    cls.storage = de_test_object.DetectStorage()
    cls.container_id = (
        '7b02fb3e8a665a63e32b909af5babb7d6ba0b64e10003b2d9534c7d5f2af8966')
    cls.image_id = (
        '7968321274dc6b6171697c33df7815310468e694ac5be0ec03ff053bb135e768')

  @classmethod
  def tearDownClass(cls):
    shutil.rmtree(os.path.join('test_data', 'docker'))

  def testDetectStorage(self):
    de_test_object = de.DockerExplorer()

    de_test_object.docker_directory = 'this_dir_shouldnt_exist'
    expected_error_message = (
        '{0:s} is not a Docker directory\n'
        'Please specify the Docker\'s directory path.\n'
        'hint: python {1:s} -r /var/lib/docker').format(
            de_test_object.docker_directory, sys.argv[0])

    with self.assertRaises(de.BadStorageException) as err:
      de_test_object.DetectStorage()
    self.assertEqual(expected_error_message, err.exception.message)

    de_test_object.docker_directory = os.path.join('test_data', 'docker')
    storage_object = de_test_object.DetectStorage()
    self.assertIsNotNone(storage_object)
    self.assertIsInstance(storage_object, aufs.AufsStorage)
    self.assertEqual(storage_object.STORAGE_METHOD, 'aufs')

    self.assertEqual(2, storage_object.docker_version)
    self.assertEqual('config.v2.json',
                     storage_object.container_config_filename)

  def testGetContainerInfo(self):

    list_container_info = self.storage.GetAllContainersInfo()
    self.assertEqual(7, len(list_container_info))

    container_info = list_container_info[4]

    self.assertEqual('/dreamy_snyder', container_info.name)
    self.assertEqual('2017-02-13T16:45:05.629904159Z',
                     container_info.creation_timestamp)
    self.assertEqual('busybox', container_info.config_image_name)
    self.assertTrue(container_info.running)

    container_id = container_info.container_id
    self.assertTrue(self.container_id, container_id)

  def testGetOrderedLayers(self):
    layers = self.storage.GetOrderedLayers(self.container_id)
    self.assertEqual(1, len(layers))
    self.assertEqual('sha256:{0:s}'.format(self.image_id), layers[0])

  def testGetRunningContainersList(self):
    running_containers = self.storage.GetContainersList(only_running=True)
    self.assertEqual(1, len(running_containers))
    container = running_containers[0]
    self.assertEqual('/dreamy_snyder', container.name)
    self.assertEqual(
        '2017-02-13T16:45:05.629904159Z', container.creation_timestamp)
    self.assertEqual('busybox', container.config_image_name)
    self.assertTrue(container.running)

  def testListRunningContainers(self):
    result_string = self.storage.ShowContainers(only_running=True)
    expected_string = (
        'Container id: {0:s} / No Label\n'
        '\tStart date: 2017-02-13T16:45:05.785658\n'
        '\tImage ID: {1:s}\n'
        '\tImage Name: busybox\n').format(self.container_id, self.image_id)
    self.assertEqual(expected_string, result_string)

  def testGetLayerInfo(self):
    layer_info = self.storage.GetLayerInfo(
        'sha256:{0:s}'.format(self.image_id))
    self.assertEqual('2017-01-13T22:13:54.401355854Z', layer_info['created'])
    self.assertEqual(['/bin/sh', '-c', '#(nop) ', 'CMD ["sh"]'],
                     layer_info['container_config']['Cmd'])

  def testListRepositories(self):
    result_string = self.storage.ShowRepositories()
    expected_string = (
        'Listing repositories from file '
        'test_data/docker/image/aufs/repositories.json{\n'
        '    "Repositories": {\n'
        '        "busybox": {\n'
        '            "busybox:latest": "sha256:%s"\n'
        '        }\n'
        '    }\n'
        '}')%self.image_id
    self.assertEqual(expected_string, result_string)

  def testMakeMountCommands(self):
    test_mount_dir = '/mnt'
    commands = self.storage.MakeMountCommands(
        self.container_id, test_mount_dir)
    expected_commands = [
        ('mount -t aufs -o ro,br=test_data/docker/aufs/diff/test_data/docker/'
         'aufs/diff/'
         'b16a494082bba0091e572b58ff80af1b7b5d28737a3eedbe01e73cd7f4e01d23'
         '=ro+wh none {0:s}').format(test_mount_dir),
        ('mount -t aufs -o ro,remount,append:test_data/docker/aufs/diff/'
         'b16a494082bba0091e572b58ff80af1b7b5d28737a3eedbe01e73cd7f4e01d23'
         '-init=ro+wh none {0:s}').format(test_mount_dir),
        ('mount -t aufs -o ro,remount,append:test_data/docker/aufs/diff/'
         'd1c54c46d331de21587a16397e8bd95bdbb1015e1a04797c76de128107da83ae'
         '=ro+wh none {0:s}').format(test_mount_dir),
        ('mount --bind -o ro {0:s}/docker/volumes/'
         '28297de547b5473a9aff90aaab45ed108ebf019981b40c3c35c226f54c13ac0d/'
         '_data {1:s}/var/jenkins_home').format(
             os.path.abspath('test_data'), test_mount_dir)
    ]
    self.assertEqual(expected_commands, commands)


class TestOverlayStorage(unittest.TestCase):
  """Tests methods in the OverlayStorage object."""

  @classmethod
  def setUpClass(cls):
    docker_directory_path = os.path.join('test_data', 'docker')
    if not os.path.isdir(docker_directory_path):
      docker_tar = os.path.join('test_data', 'overlay.tgz')
      tar = tarfile.open(docker_tar, 'r:gz')
      tar.extractall('test_data')
      tar.close()

    de_test_object = de.DockerExplorer()
    de_test_object.docker_directory = docker_directory_path
    cls.storage = de_test_object.DetectStorage()
    cls.container_id = (
        '5dc287aa80b460652a5584e80a5c8c1233b0c0691972d75424cf5250b917600a')
    cls.image_id = (
        '5b0d59026729b68570d99bc4f3f7c31a2e4f2a5736435641565d93e7c25bd2c3')

  @classmethod
  def tearDownClass(cls):
    shutil.rmtree(os.path.join('test_data', 'docker'))

  def testDetectStorage(self):
    de_test_object = de.DockerExplorer()

    de_test_object.docker_directory = 'this_dir_shouldnt_exist'
    expected_error_message = (
        '{0:s} is not a Docker directory\n'
        'Please specify the Docker\'s directory path.\n'
        'hint: python {1:s} -r /var/lib/docker').format(
            de_test_object.docker_directory, sys.argv[0])

    with self.assertRaises(de.BadStorageException) as err:
      de_test_object.DetectStorage()
    self.assertEqual(expected_error_message, err.exception.message)

    de_test_object.docker_directory = os.path.join('test_data', 'docker')
    storage_object = de_test_object.DetectStorage()
    self.assertIsNotNone(storage_object)
    self.assertIsInstance(storage_object, overlay.OverlayStorage)
    self.assertEqual(storage_object.STORAGE_METHOD, 'overlay')

    self.assertEqual(2, storage_object.docker_version)
    self.assertEqual('config.v2.json',
                     storage_object.container_config_filename)

  def testGetContainerInfo(self):

    list_container_info = self.storage.GetAllContainersInfo()
    self.assertEqual(6, len(list_container_info))

    container_info = list_container_info[4]

    self.assertEqual('/elastic_booth', container_info.name)
    self.assertEqual('2018-01-26T14:55:56.280943771Z',
                     container_info.creation_timestamp)
    self.assertEqual('busybox:latest', container_info.config_image_name)
    self.assertTrue(container_info.running)

    container_id = container_info.container_id
    self.assertTrue(self.container_id, container_id)

  def testGetOrderedLayers(self):
    layers = self.storage.GetOrderedLayers(self.container_id)
    self.assertEqual(1, len(layers))
    self.assertEqual('sha256:{0:s}'.format(self.image_id), layers[0])

  def testGetRunningContainersList(self):
    running_containers = self.storage.GetContainersList(only_running=True)
    self.assertEqual(1, len(running_containers))
    container = running_containers[0]
    self.assertEqual('/elastic_booth', container.name)
    self.assertEqual(
        '2018-01-26T14:55:56.280943771Z', container.creation_timestamp)
    self.assertEqual('busybox:latest', container.config_image_name)

    self.assertTrue(container.running)

  def testListRunningContainers(self):
    result_string = self.storage.ShowContainers(only_running=True)
    expected_string = (
        'Container id: {0:s} / No Label\n'
        '\tStart date: 2018-01-26T14:55:56.574924\n'
        '\tImage ID: {1:s}\n'
        '\tImage Name: busybox:latest\n').format(
            self.container_id, self.image_id)
    self.assertEqual(expected_string, result_string)

  def testGetLayerInfo(self):
    layer_info = self.storage.GetLayerInfo(
        'sha256:{0:s}'.format(self.image_id))
    self.assertEqual('2018-01-24T04:29:35.590938514Z', layer_info['created'])
    self.assertEqual(['/bin/sh', '-c', '#(nop) ', 'CMD ["sh"]'],
                     layer_info['container_config']['Cmd'])

  def testListRepositories(self):
    result_string = self.storage.ShowRepositories()
    self.maxDiff = None
    expected_string = (
        'Listing repositories from file '
        'test_data/docker/image/overlay/repositories.json{\n'
        '    "Repositories": {\n'
        '        "busybox": {\n'
        '            "busybox:latest": "sha256:%s", \n'
        '            "busybox@sha256:1669a6aa7350e1cdd28f972ddad5aceba2912f589'
        'f19a090ac75b7083da748db": '
        '"sha256:5b0d59026729b68570d99bc4f3f7c31a2e4f2a5736435641565d93e7c25bd'
        '2c3"\n'
        '        }\n'
        '    }\n'
        '}')%self.image_id
    self.assertEqual(expected_string, result_string)

  def testMakeMountCommands(self):
    test_mount_dir = '/mnt'
    commands = self.storage.MakeMountCommands(
        self.container_id, test_mount_dir)
    expected_commands = [(
        'mount -t overlay overlay -o ro,lowerdir='
        '"test_data/docker/overlay/a94d714512251b0d8a9bfaacb832e0c6cb70f71cb71'
        '976cca7a528a429336aae/root":'
        '"test_data/docker/overlay/974e2b994f9db74e1ddd6fc546843bc65920e786612'
        'a388f25685acf84b3fed1/upper",'
        'workdir="test_data/docker/overlay/974e2b994f9db74e1ddd6fc546843bc6592'
        '0e786612a388f25685acf84b3fed1/work" "/mnt"')]
    self.assertEqual(expected_commands, commands)

class TestOverlay2Storage(unittest.TestCase):
  """Tests methods in the Overlay2Storage object."""

  @classmethod
  def setUpClass(cls):
    docker_directory_path = os.path.join('test_data', 'docker')
    if not os.path.isdir(docker_directory_path):
      docker_tar = os.path.join('test_data', 'overlay2.tgz')
      tar = tarfile.open(docker_tar, 'r:gz')
      tar.extractall('test_data')
      tar.close()

    de_test_object = de.DockerExplorer()
    de_test_object.docker_directory = docker_directory_path
    cls.storage = de_test_object.DetectStorage()
    cls.container_id = (
        '8e8b7f23eb7cbd4dfe7e91646ddd0e0f524218e25d50113559f078dfb2690206')
    cls.image_id = (
        '8ac48589692a53a9b8c2d1ceaa6b402665aa7fe667ba51ccc03002300856d8c7')

  @classmethod
  def tearDownClass(cls):
    shutil.rmtree(os.path.join('test_data', 'docker'))

  def testDetectStorage(self):
    de_test_object = de.DockerExplorer()

    de_test_object.docker_directory = 'this_dir_shouldnt_exist'
    expected_error_message = (
        '{0:s} is not a Docker directory\n'
        'Please specify the Docker\'s directory path.\n'
        'hint: python {1:s} -r /var/lib/docker').format(
            de_test_object.docker_directory, sys.argv[0])

    with self.assertRaises(de.BadStorageException) as err:
      de_test_object.DetectStorage()
    self.assertEqual(expected_error_message, err.exception.message)

    de_test_object.docker_directory = os.path.join('test_data', 'docker')
    storage_object = de_test_object.DetectStorage()
    self.assertIsNotNone(storage_object)
    self.assertIsInstance(storage_object, overlay.OverlayStorage)
    self.assertEqual(storage_object.STORAGE_METHOD, 'overlay2')

    self.assertEqual(2, storage_object.docker_version)
    self.assertEqual('config.v2.json',
                     storage_object.container_config_filename)

  def testGetContainerInfo(self):

    list_container_info = self.storage.GetAllContainersInfo()
    self.assertEqual(5, len(list_container_info))

    container_info = list_container_info[0]

    self.assertEqual('/festive_perlman', container_info.name)
    self.assertEqual('2018-05-16T10:51:39.271019533Z',
                     container_info.creation_timestamp)
    self.assertEqual('busybox', container_info.config_image_name)
    self.assertTrue(container_info.running)
    container_id = container_info.container_id
    self.assertTrue(self.container_id, container_id)

  def testGetOrderedLayers(self):
    layers = self.storage.GetOrderedLayers(self.container_id)
    self.assertEqual(1, len(layers))
    self.assertEqual('sha256:{0:s}'.format(self.image_id), layers[0])

  def testGetRunningContainersList(self):
    running_containers = self.storage.GetContainersList(only_running=True)
    self.assertEqual(1, len(running_containers))
    container = running_containers[0]
    self.assertEqual('/festive_perlman', container.name)
    self.assertEqual(
        '2018-05-16T10:51:39.271019533Z', container.creation_timestamp)
    self.assertEqual('busybox', container.config_image_name)

    self.assertTrue(container.running)

  def testListRunningContainers(self):
    result_string = self.storage.ShowContainers(only_running=True)
    expected_string = (
        'Container id: {0:s} / No Label\n'
        '\tStart date: 2018-05-16T10:51:39.625989\n'
        '\tImage ID: {1:s}\n'
        '\tImage Name: busybox\n').format(
            self.container_id, self.image_id)
    self.assertEqual(expected_string, result_string)

  def testGetLayerInfo(self):
    layer_info = self.storage.GetLayerInfo(
        'sha256:{0:s}'.format(self.image_id))
    self.assertEqual('2018-04-05T10:41:28.876407948Z', layer_info['created'])
    self.assertEqual(['/bin/sh', '-c', '#(nop) ', 'CMD ["sh"]'],
                     layer_info['container_config']['Cmd'])

  def testListRepositories(self):
    result_string = self.storage.ShowRepositories()
    self.maxDiff = None
    expected_string = (
        'Listing repositories from file '
        'test_data/docker/image/overlay2/repositories.json{\n'
        '    "Repositories": {\n'
        '        "busybox": {\n'
        '            "busybox:latest": "sha256:%s", \n'
        '            "busybox@sha256:58ac43b2cc92c687a32c8be6278e50a063579655fe'
        '3090125dcb2af0ff9e1a64": '
        '"sha256:8ac48589692a53a9b8c2d1ceaa6b402665aa7fe667ba51ccc03002300856d8'
        'c7"\n'
        '        }\n'
        '    }\n'
        '}')%self.image_id
    self.assertEqual(expected_string, result_string)

  def testMakeMountCommands(self):
    self.maxDiff = None
    test_mount_dir = '/mnt'
    commands = self.storage.MakeMountCommands(
        self.container_id, test_mount_dir)
    expected_commands = [(
        'mount -t overlay overlay -o ro,lowerdir='
        '"test_data/docker/overlay2/l/OTFSLJCXWCECIG6FVNGRTWUZ7D:'
        'test_data/docker/overlay2/l/CH5A7XWSBP2DUPV7V47B7DOOGY":'
        '"test_data/docker/overlay2/'
        '92fd3b3e7d6101bb701743c9518c45b0d036b898c8a3d7cae84e1a06e6829b53/diff"'
        ',workdir="test_data/docker/overlay2/'
        '92fd3b3e7d6101bb701743c9518c45b0d036b898c8a3d7cae84e1a06e6829b53/work"'
        ' "/mnt"'
        )]
    self.assertEqual(expected_commands, commands)

if __name__ == '__main__':
  unittest.main()
