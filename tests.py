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

import os
import shutil
import sys
import tarfile
import unittest

import mock
try:
  from StringIO import StringIO
except ImportError:
  from io import StringIO

from docker_explorer import container
from docker_explorer import errors
from docker_explorer import explorer
from docker_explorer import storage
from docker_explorer import utils
from tools import de


# pylint: disable=protected-access

class UtilsTests(unittest.TestCase):
  """Tests Utils methods."""

  def testFormatDatetime(self):
    """Tests the utils.FormatDatetime function."""
    test_date = '2017-12-25T15:59:59.102938 msqedigrb msg'
    expected_time_str = '2017-12-25T15:59:59.102938'
    self.assertEqual(expected_time_str, utils.FormatDatetime(test_date))

  def testPrettyPrintJSON(self):
    """Tests the utils.PrettyPrintJSON function."""
    test_dict = {'test': [{'dict1': {'key1': 'val1'}, 'dict2': None}]}
    expected_string = ('{\n    "test": [\n        {\n            "dict1": {\n'
                       '                "key1": "val1"\n            }, \n'
                       '            "dict2": null\n        }\n    ]\n}\n')
    self.assertEqual(expected_string, utils.PrettyPrintJSON(test_dict))


class TestDEMain(unittest.TestCase):
  """Tests DockerExplorerTool object methods."""

  @classmethod
  def tearDownClass(cls):
    shutil.rmtree(cls.docker_directory_path)

  @classmethod
  def setUpClass(cls):
    # We setup one overlay2 backed Docker root folder for all the following
    # tests.
    cls.driver = 'overlay2'
    cls.docker_directory_path = os.path.join('test_data', 'docker')
    if not os.path.isdir(cls.docker_directory_path):
      docker_tar = os.path.join('test_data', 'overlay2.v2.tgz')
      tar = tarfile.open(docker_tar, 'r:gz')
      tar.extractall('test_data')
      tar.close()
    cls.explorer_object = explorer.Explorer()
    cls.explorer_object.SetDockerDirectory(cls.docker_directory_path)
    cls.explorer_object.DetectDockerStorageVersion()

  def testParseArguments(self):
    """Tests the DockerExplorerTool.ParseArguments function."""
    de_object = de.DockerExplorerTool()

    prog = sys.argv[0]

    expected_docker_root = os.path.join('test_data', 'docker')

    args = [prog, '-r', expected_docker_root, 'list', 'repositories']
    sys.argv = args

    options = de_object.ParseArguments()
    usage_string = de_object._argument_parser.format_usage()
    expected_usage = '[-h] [-r DOCKER_DIRECTORY] [-V] {mount,list,history}'
    self.assertTrue(expected_usage in usage_string)
    self.assertEqual(expected_docker_root, options.docker_directory)

  def testShowHistory(self):
    """Tests that ShowHistory shows history."""
    de_object = de.DockerExplorerTool()
    de_object._explorer = self.explorer_object
    # We pick one of the container IDs.
    container_id = container.GetAllContainersIDs(self.docker_directory_path)[0]
    with mock.patch('sys.stdout', new=StringIO()) as fake_output:
      de_object.docker_directory = self.docker_directory_path
      de_object.ShowHistory(container_id)
      expected_string = """{
    "sha256:8ac48589692a53a9b8c2d1ceaa6b402665aa7fe667ba51ccc03002300856d8c7": {
        "container_cmd": "/bin/sh -c #(nop)  CMD [\\"sh\\"]", 
        "created_at": "2018-04-05T10:41:28.876407", 
        "size": 0
    }
}

"""
      self.assertEqual(
          expected_string, fake_output.getvalue())

  def testShowContainers(self):
    """Tests that ShowHistory shows history."""
    de_object = de.DockerExplorerTool()
    de_object._explorer = self.explorer_object
    self.maxDiff = None
    with mock.patch('sys.stdout', new=StringIO()) as fake_output:
      de_object.docker_directory = self.docker_directory_path
      de_object.ShowContainers()
      expected_string = """[
    {
        "container_id": "10acac0b3466813c9e1f85e2aa7d06298e51fbfe86bbcb6b7a19dd\
33d3798f6a", 
        "image_id": "8ac48589692a53a9b8c2d1ceaa6b402665aa7fe667ba51ccc030023008\
56d8c7", 
        "image_name": "busybox", 
        "mount_id": "d877fe1ffb0a1da27204bc1ae4e356c7a7a235e7392d04a81d5d7df347\
1c74b6", 
        "start_date": "0001-01-01T00:00:00"
    }, 
    {
        "container_id": "61ba4e6c012c782186c649466157e05adfd7caa5b551432de51043\
893cae5353", 
        "image_id": "8ac48589692a53a9b8c2d1ceaa6b402665aa7fe667ba51ccc030023008\
56d8c7", 
        "image_name": "busybox", 
        "mount_id": "04cc041c6e1a41007c2c7f19574194244e81ea7dc0b3c32848b9e06915\
065cc4", 
        "start_date": "0001-01-01T00:00:00"
    }, 
    {
        "container_id": "9949fa153b778e39d6cab0a4e0ba60fa34a13fedb1f256d613a2f8\
8c0c98408a", 
        "image_id": "8ac48589692a53a9b8c2d1ceaa6b402665aa7fe667ba51ccc030023008\
56d8c7", 
        "image_name": "busybox", 
        "mount_id": "fc790748d90675e0934c6ade53f68b6f73b920ca1f08df718c272e51ab\
dabea7", 
        "start_date": "2018-05-16T10:50:57.324126"
    }, 
    {
        "container_id": "f83f963c67cbd36055f690fc988c1e42be06c1253e80113d1d5167\
78c06b2841", 
        "image_id": "8ac48589692a53a9b8c2d1ceaa6b402665aa7fe667ba51ccc030023008\
56d8c7", 
        "image_name": "busybox", 
        "mount_id": "8ed5fc296a7930f4faf7812c081cb1b310dfc29f6b23f5f2425e36f51d\
5cb9d1", 
        "start_date": "2018-05-16T10:51:05.177987"
    }, 
    {
        "container_id": "8e8b7f23eb7cbd4dfe7e91646ddd0e0f524218e25d50113559f078\
dfb2690206", 
        "image_id": "8ac48589692a53a9b8c2d1ceaa6b402665aa7fe667ba51ccc030023008\
56d8c7", 
        "image_name": "busybox", 
        "mount_id": "92fd3b3e7d6101bb701743c9518c45b0d036b898c8a3d7cae84e1a06e6\
829b53", 
        "start_date": "2018-05-16T10:51:39.625989"
    }
]

"""
      self.assertEqual(expected_string, fake_output.getvalue())

  def testDetectStorageFail(self):
    """Tests that the DockerExplorerTool.DetectStorage function fails on
    Docker directory."""
    explorer_object = explorer.Explorer()
    explorer_object.docker_directory = 'this_dir_shouldnt_exist'

    expected_error_message = (
        'this_dir_shouldnt_exist is not a Docker directory')
    with self.assertRaises(errors.BadStorageException) as err:
      explorer_object.SetDockerDirectory('this_dir_shouldnt_exist')
    self.assertEqual(expected_error_message, err.exception.message)


class DockerTestCase(unittest.TestCase):
  """Base class for tests of different Storage implementations."""

  @classmethod
  def tearDownClass(cls):
    shutil.rmtree(os.path.join('test_data', 'docker'))

  @classmethod
  def _setup(cls, driver, driver_class, storage_version=2):
    """Internal method to set up the TestCase on a specific storage."""
    cls.driver = driver
    docker_directory_path = os.path.join('test_data', 'docker')
    if not os.path.isdir(docker_directory_path):
      docker_tar = os.path.join(
          'test_data', '{0:s}.v{1:d}.tgz'.format(driver, storage_version))
      tar = tarfile.open(docker_tar, 'r:gz')
      tar.extractall('test_data')
      tar.close()
    cls.explorer_object = explorer.Explorer()
    cls.explorer_object.SetDockerDirectory(docker_directory_path)
    cls.explorer_object.DetectDockerStorageVersion()

    cls.driver_class = driver_class
    cls.storage_version = storage_version

  def testDetectStorage(self):
    """Tests the Explorer.DetectStorage function."""
    for container_obj in self.explorer_object.GetAllContainers():
      self.assertIsNotNone(container_obj.storage_object)
      self.assertEqual(container_obj.storage_name, self.driver)
      self.assertIsInstance(container_obj.storage_object, self.driver_class)

      self.assertEqual(self.storage_version, container_obj.docker_version)
      if self.storage_version == 1:
        self.assertEqual(
            'config.json', container_obj.container_config_filename)
      elif self.storage_version == 2:
        self.assertEqual(
            'config.v2.json', container_obj.container_config_filename)

class TestAufsStorage(DockerTestCase):
  """Tests methods in the BaseStorage object."""

  @classmethod
  def setUpClass(cls):
    cls._setup('aufs', storage.AufsStorage)

  def testGetAllContainers(self):
    """Tests the GetAllContainers function on a AuFS storage."""
    containers_list = self.explorer_object.GetAllContainers()
    containers_list = sorted(containers_list, key=lambda ci: ci.name)
    self.assertEqual(7, len(containers_list))

    container_obj = containers_list[1]

    self.assertEqual('/dreamy_snyder', container_obj.name)
    self.assertEqual('2017-02-13T16:45:05.629904159Z',
                     container_obj.creation_timestamp)
    self.assertEqual('busybox', container_obj.config_image_name)
    self.assertTrue(container_obj.running)

    self.assertEqual(
        '7b02fb3e8a665a63e32b909af5babb7d6ba0b64e10003b2d9534c7d5f2af8966',
        container_obj.container_id)

  def testGetOrderedLayers(self):
    """Tests the BaseStorage.GetOrderedLayers function on a AuFS storage."""
    container_obj = self.explorer_object.GetContainer(
        '7b02fb3e8a665a63e32b909af5babb7d6ba0b64e10003b2d9534c7d5f2af8966')
    layers = container_obj.GetOrderedLayers()
    self.assertEqual(1, len(layers))
    self.assertEqual(
        'sha256:'
        '7968321274dc6b6171697c33df7815310468e694ac5be0ec03ff053bb135e768',
        layers[0])

  def testGetRunningContainersList(self):
    """Tests the BaseStorage.GetContainersList function on a AuFS storage."""
    running_containers = self.explorer_object.GetContainersList(
        only_running=True)
    running_containers = sorted(
        running_containers, key=lambda ci: ci.container_id)
    self.assertEqual(1, len(running_containers))
    container_obj = running_containers[0]
    self.assertEqual('/dreamy_snyder', container_obj.name)
    self.assertEqual(
        '2017-02-13T16:45:05.629904159Z', container_obj.creation_timestamp)
    self.assertEqual('busybox', container_obj.config_image_name)
    self.assertTrue(container_obj.running)

  def testGetContainersJson(self):
    """Tests the GetContainersJson function on a AuFS storage."""
    result = self.explorer_object.GetContainersJson(only_running=True)
    expected = [
        {'image_id':
         '7968321274dc6b6171697c33df7815310468e694ac5be0ec03ff053bb135e768',
         'container_id':
         '7b02fb3e8a665a63e32b909af5babb7d6ba0b64e10003b2d9534c7d5f2af8966',
         'mount_id':
         'b16a494082bba0091e572b58ff80af1b7b5d28737a3eedbe01e73cd7f4e01d23',
         'start_date': '2017-02-13T16:45:05.785658',
         'image_name': 'busybox'}
    ]
    self.assertEqual(expected, result)

  def testGetLayerInfo(self):
    """Tests the BaseStorage.GetLayerInfo function on a AuFS storage."""
    container_obj = self.explorer_object.GetContainer(
        '7b02fb3e8a665a63e32b909af5babb7d6ba0b64e10003b2d9534c7d5f2af8966')
    layer_info = container_obj.GetLayerInfo(
        'sha256:'
        '7968321274dc6b6171697c33df7815310468e694ac5be0ec03ff053bb135e768')
    self.assertEqual('2017-01-13T22:13:54.401355854Z', layer_info['created'])
    self.assertEqual(['/bin/sh', '-c', '#(nop) ', 'CMD ["sh"]'],
                     layer_info['container_config']['Cmd'])

  def testGetRepositoriesString(self):
    """Tests GetRepositoriesString() on a AuFS storage."""
    self.maxDiff = None
    result_string = self.explorer_object.GetRepositoriesString()
    expected_string = (
        '[\n'
        '    {\n'
        '        "Repositories": {\n'
        '            "busybox": {\n'
        '                "busybox:latest": "sha256:'
        '7968321274dc6b6171697c33df7815310468e694ac5be0ec03ff053bb135e768"\n'
        '            }\n'
        '        }, \n'
        '        "path": "test_data/docker/image/aufs/repositories.json"\n'
        '    }\n'
        ']\n'
    )
    self.assertEqual(expected_string, result_string)

  def testMakeMountCommands(self):
    """Tests the BaseStorage.MakeMountCommands function on a AuFS storage."""
    container_obj = self.explorer_object.GetContainer(
        '7b02fb3e8a665a63e32b909af5babb7d6ba0b64e10003b2d9534c7d5f2af8966')
    commands = container_obj.storage_object.MakeMountCommands(
        container_obj, '/mnt')
    commands = [' '.join(x) for x in commands]
    expected_commands = [
        ('/bin/mount -t aufs -o ro,br=test_data/docker/aufs/diff/test_data/'
         'docker/aufs/diff/'
         'b16a494082bba0091e572b58ff80af1b7b5d28737a3eedbe01e73cd7f4e01d23'
         '=ro+wh none /mnt'),
        ('/bin/mount -t aufs -o ro,remount,append:test_data/docker/aufs/diff/'
         'b16a494082bba0091e572b58ff80af1b7b5d28737a3eedbe01e73cd7f4e01d23'
         '-init=ro+wh none /mnt'),
        ('/bin/mount -t aufs -o ro,remount,append:test_data/docker/aufs/diff/'
         'd1c54c46d331de21587a16397e8bd95bdbb1015e1a04797c76de128107da83ae'
         '=ro+wh none /mnt'),
        ('/bin/mount --bind -o ro {0:s}/docker/volumes/'
         '28297de547b5473a9aff90aaab45ed108ebf019981b40c3c35c226f54c13ac0d/'
         '_data /mnt/var/jenkins_home').format(os.path.abspath('test_data'))
    ]
    self.assertEqual(expected_commands, commands)

  def testGetHistory(self):
    """Tests the BaseStorage.GetHistory function on a AuFS storage."""
    self.maxDiff = None
    container_obj = self.explorer_object.GetContainer(
        '7b02fb3e8a665a63e32b909af5babb7d6ba0b64e10003b2d9534c7d5f2af8966')
    expected = {
        'sha256:'
        '7968321274dc6b6171697c33df7815310468e694ac5be0ec03ff053bb135e768': {
            'created_at': '2017-01-13T22:13:54.401355',
            'container_cmd': '/bin/sh -c #(nop)  CMD ["sh"]',
            'size': 0
        }
    }

    self.assertEqual(expected, container_obj.GetHistory())

  def testGetFullContainerID(self):
    """Tests the DockerExplorerTool._GetFullContainerID function on AuFS."""
    self.assertEqual(
        '2cc4b0d9c1dfdf71099c5e9a109e6a0fe286152a5396bd1850689478e8f70625',
        self.explorer_object._GetFullContainerID('2cc4b0d'))

    with self.assertRaises(Exception) as err:
      self.explorer_object._GetFullContainerID('')
    self.assertEqual(
        'Too many container IDs starting with "": '
        '1171e9631158156ba2b984d335b2bf31838403700df3882c51aed70beebb604f, '
        '2cc4b0d9c1dfdf71099c5e9a109e6a0fe286152a5396bd1850689478e8f70625, '
        '7b02fb3e8a665a63e32b909af5babb7d6ba0b64e10003b2d9534c7d5f2af8966, '
        '986c6e682f30550512bc2f7243f5a57c91b025e543ef703c426d732585209945, '
        'b6f881bfc566ed604da1dc9bc8782a3540380c094154d703a77113b1ecfca660, '
        'c8a38b6c29b0c901c37c2bb17bfcd73942c44bb71cc528505385c62f3c6fff35, '
        'dd39804186d4f649f1e9cec89df1583e7a12a48193223a16cc40958f7e76b858',
        err.exception.message)

    with self.assertRaises(Exception) as err:
      self.explorer_object._GetFullContainerID('xx')
    self.assertEqual(
        'Could not find any container ID starting with "xx"',
        err.exception.message)


class TestAufsV1Storage(DockerTestCase):
  """Tests methods in the BaseStorage object."""

  @classmethod
  def setUpClass(cls):
    cls._setup('aufs', storage.AufsStorage, storage_version=1)

  def testGetAllContainers(self):
    """Tests the GetAllContainers function on a AuFS storage."""
    containers_list = self.explorer_object.GetAllContainers()
    containers_list = sorted(containers_list, key=lambda ci: ci.name)
    self.assertEqual(3, len(containers_list))

    container_obj = containers_list[0]

    self.assertEqual('/angry_rosalind', container_obj.name)
    self.assertEqual('2018-12-27T10:53:17.096746609Z',
                     container_obj.creation_timestamp)
    self.assertEqual('busybox', container_obj.config_image_name)
    self.assertTrue(container_obj.running)

    self.assertEqual(
        'de44dd97cfd1c8d1c1aad7f75a435603991a7a39fa4f6b20a69bf4458809209c',
        container_obj.container_id)

  def testGetOrderedLayers(self):
    """Tests the BaseStorage.GetOrderedLayers function on a AuFS storage."""
    container_obj = self.explorer_object.GetContainer(
        'de44dd97cfd1c8d1c1aad7f75a435603991a7a39fa4f6b20a69bf4458809209c')
    layers = container_obj.GetOrderedLayers()
    self.assertEqual(2, len(layers))
    self.assertEqual(
        '1cee97b18f87b5fa91633db35f587e2c65c093facfa2cbbe83d5ebe06e1d9125',
        layers[0])

  def testGetRunningContainersList(self):
    """Tests the BaseStorage.GetContainersList function on a AuFS storage."""
    running_containers = self.explorer_object.GetContainersList(
        only_running=True)
    running_containers = sorted(
        running_containers, key=lambda ci: ci.container_id)
    self.assertEqual(1, len(running_containers))
    container_obj = running_containers[0]
    self.assertEqual('/angry_rosalind', container_obj.name)
    self.assertEqual(
        '2018-12-27T10:53:17.096746609Z', container_obj.creation_timestamp)
    self.assertEqual('busybox', container_obj.config_image_name)
    self.assertTrue(container_obj.running)

  def testGetContainersJson(self):
    """Tests the GetContainersJson function on a AuFS storage."""
    result = self.explorer_object.GetContainersJson(only_running=True)
    expected = [
        {'image_id':
         '1cee97b18f87b5fa91633db35f587e2c65c093facfa2cbbe83d5ebe06e1d9125',
         'container_id':
         'de44dd97cfd1c8d1c1aad7f75a435603991a7a39fa4f6b20a69bf4458809209c',
         'start_date': '2018-12-27T10:53:17.409426',
         'image_name': 'busybox'}
    ]
    self.assertEqual(expected, result)

  def testGetLayerInfo(self):
    """Tests the BaseStorage.GetLayerInfo function on a AuFS storage."""
    container_obj = self.explorer_object.GetContainer(
        'de44dd97cfd1c8d1c1aad7f75a435603991a7a39fa4f6b20a69bf4458809209c')
    layer_info = container_obj.GetLayerInfo(
        '1cee97b18f87b5fa91633db35f587e2c65c093facfa2cbbe83d5ebe06e1d9125')
    self.assertEqual('2018-12-26T08:20:42.831353376Z', layer_info['created'])
    self.assertEqual(['/bin/sh', '-c', '#(nop) ', 'CMD ["sh"]'],
                     layer_info['container_config']['Cmd'])

  def testGetRepositoriesString(self):
    """Tests GetRepositoriesString() on a AuFS storage."""
    self.maxDiff = None
    result_string = self.explorer_object.GetRepositoriesString()
    expected_string = (
        '[\n'
        '    {\n'
        '        "Repositories": {\n'
        '            "busybox": {\n'
        '                "latest": "'
        '1cee97b18f87b5fa91633db35f587e2c65c093facfa2cbbe83d5ebe06e1d9125"\n'
        '            }\n'
        '        }, \n'
        '        "path": "test_data/docker/repositories-aufs"\n'
        '    }\n'
        ']\n'
    )
    self.assertEqual(expected_string, result_string)

  def testMakeMountCommands(self):
    """Tests the BaseStorage.MakeMountCommands function on a AuFS storage."""
    container_obj = self.explorer_object.GetContainer(
        'de44dd97cfd1c8d1c1aad7f75a435603991a7a39fa4f6b20a69bf4458809209c')
    commands = container_obj.storage_object.MakeMountCommands(
        container_obj, '/mnt')
    commands = [' '.join(x) for x in commands]
    expected_commands = [
        ('/bin/mount -t aufs -o ro,br=test_data/'
         'docker/aufs/diff/'
         'de44dd97cfd1c8d1c1aad7f75a435603991a7a39fa4f6b20a69bf4458809209c'
         '=ro+wh none /mnt'),
        ('/bin/mount -t aufs -o ro,remount,append:test_data/docker/aufs/diff/'
         'de44dd97cfd1c8d1c1aad7f75a435603991a7a39fa4f6b20a69bf4458809209c'
         '-init=ro+wh none /mnt'),
        ('/bin/mount -t aufs -o ro,remount,append:test_data/docker/aufs/diff/'
         '1cee97b18f87b5fa91633db35f587e2c65c093facfa2cbbe83d5ebe06e1d9125'
         '=ro+wh none /mnt'),
        ('/bin/mount -t aufs -o ro,remount,append:test_data/docker/aufs/diff/'
         'df557f39d413a1408f5c28d8aab2892f927237ec22e903ef04b331305130ab38'
         '=ro+wh none /mnt')
    ]
    self.assertEqual(expected_commands, commands)

  def testGetHistory(self):
    """Tests the BaseStorage.GetHistory function on a AuFS storage."""
    self.maxDiff = None
    container_obj = self.explorer_object.GetContainer(
        'de44dd97cfd1c8d1c1aad7f75a435603991a7a39fa4f6b20a69bf4458809209c')
    expected = {
        '1cee97b18f87b5fa91633db35f587e2c65c093facfa2cbbe83d5ebe06e1d9125': {
            'size': 0},
        'df557f39d413a1408f5c28d8aab2892f927237ec22e903ef04b331305130ab38': {
            'created_at': '2018-12-26T08:20:42.687925',
            'container_cmd':
                ('/bin/sh -c #(nop) ADD file:ce026b62356eec3ad1214f92be2c'
                 '9dc063fe205bd5e600be3492c4dfb17148bd in / '),
            'size': 1154361}
    }

    self.assertEqual(expected, container_obj.GetHistory())

  def testGetFullContainerID(self):
    """Tests the DockerExplorerTool._GetFullContainerID function on AuFS."""
    self.assertEqual(
        'de44dd97cfd1c8d1c1aad7f75a435603991a7a39fa4f6b20a69bf4458809209c',
        self.explorer_object._GetFullContainerID('de44dd'))

    self.maxDiff = None
    with self.assertRaises(Exception) as err:
      self.explorer_object._GetFullContainerID('')
    self.assertEqual(
        ('Too many container IDs starting with "": '
         '3b03d0958390ccfb92e9f1ee67de628ab315c532120d4512cb72a1805465fb35, '
         'de44dd97cfd1c8d1c1aad7f75a435603991a7a39fa4f6b20a69bf4458809209c, '
         'fbb6711cefc70193cb6cb0b113fc9ed6b9eaddcdd33667adb5cb690a4dca413a'),
        err.exception.message)

    with self.assertRaises(Exception) as err:
      self.explorer_object._GetFullContainerID('xx')
    self.assertEqual(
        'Could not find any container ID starting with "xx"',
        err.exception.message)


class TestOverlayStorage(DockerTestCase):
  """Tests methods in the OverlayStorage object."""

  @classmethod
  def setUpClass(cls):
    cls._setup('overlay', storage.OverlayStorage)

  def testGetAllContainers(self):
    """Tests the GetAllContainers function on a Overlay storage."""
    containers_list = self.explorer_object.GetAllContainers()
    containers_list = sorted(containers_list, key=lambda ci: ci.name)
    self.assertEqual(6, len(containers_list))

    container_obj = containers_list[0]

    self.assertEqual('/elastic_booth', container_obj.name)
    self.assertEqual('2018-01-26T14:55:56.280943771Z',
                     container_obj.creation_timestamp)
    self.assertEqual('busybox:latest', container_obj.config_image_name)
    self.assertTrue(container_obj.running)

    self.assertEqual(
        '5dc287aa80b460652a5584e80a5c8c1233b0c0691972d75424cf5250b917600a',
        container_obj.container_id)

  def testGetOrderedLayers(self):
    """Tests the BaseStorage.GetOrderedLayers function on a Overlay storage."""
    container_obj = self.explorer_object.GetContainer(
        '5dc287aa80b460652a5584e80a5c8c1233b0c0691972d75424cf5250b917600a')
    layers = container_obj.GetOrderedLayers()
    self.assertEqual(1, len(layers))
    self.assertEqual(
        'sha256:'
        '5b0d59026729b68570d99bc4f3f7c31a2e4f2a5736435641565d93e7c25bd2c3',
        layers[0])

  def testGetRunningContainersList(self):
    """Tests the BaseStorage.GetContainersList function on a Overlay storage."""
    running_containers = self.explorer_object.GetContainersList(
        only_running=True)
    running_containers = sorted(
        running_containers, key=lambda ci: ci.container_id)
    self.assertEqual(1, len(running_containers))
    container_obj = running_containers[0]
    self.assertEqual('/elastic_booth', container_obj.name)
    self.assertEqual(
        '2018-01-26T14:55:56.280943771Z', container_obj.creation_timestamp)
    self.assertEqual('busybox:latest', container_obj.config_image_name)

    self.assertTrue(container_obj.running)

  def testGetContainersJson(self):
    """Tests the GetContainersJson function on a Overlay storage."""
    result = self.explorer_object.GetContainersJson(only_running=True)
    expected = [
        {'image_id':
         '5b0d59026729b68570d99bc4f3f7c31a2e4f2a5736435641565d93e7c25bd2c3',
         'container_id':
         '5dc287aa80b460652a5584e80a5c8c1233b0c0691972d75424cf5250b917600a',
         'mount_id':
         '974e2b994f9db74e1ddd6fc546843bc65920e786612a388f25685acf84b3fed1',
         'start_date': '2018-01-26T14:55:56.574924',
         'image_name': 'busybox:latest'}
    ]
    self.assertEqual(expected, result)

  def testGetLayerInfo(self):
    """Tests the BaseStorage.GetLayerInfo function on a Overlay storage."""
    container_obj = self.explorer_object.GetContainer(
        '5dc287aa80b460652a5584e80a5c8c1233b0c0691972d75424cf5250b917600a')
    layer_info = container_obj.GetLayerInfo(
        'sha256:'
        '5b0d59026729b68570d99bc4f3f7c31a2e4f2a5736435641565d93e7c25bd2c3')
    self.assertEqual('2018-01-24T04:29:35.590938514Z', layer_info['created'])
    self.assertEqual(['/bin/sh', '-c', '#(nop) ', 'CMD ["sh"]'],
                     layer_info['container_config']['Cmd'])

  def testGetRepositoriesString(self):
    """Tests GetRepositoriesString() on a Overlay storage."""
    result_string = self.explorer_object.GetRepositoriesString()
    self.maxDiff = None
    expected_string = (
        '[\n'
        '    {\n'
        '        "Repositories": {\n'
        '            "busybox": {\n'
        '                "busybox:latest": "sha256:'
        '5b0d59026729b68570d99bc4f3f7c31a2e4f2a5736435641565d93e7c25bd2c3", \n'
        '                "busybox@sha256:'
        '1669a6aa7350e1cdd28f972ddad5aceba2912f589f19a090ac75b7083da748db": '
        '"sha256:'
        '5b0d59026729b68570d99bc4f3f7c31a2e4f2a5736435641565d93e7c25bd2c3"\n'
        '            }\n'
        '        }, \n'
        '        "path": "test_data/docker/image/overlay/repositories.json"\n'
        '    }\n'
        ']\n'
    )

    self.assertEqual(expected_string, result_string)

  def testMakeMountCommands(self):
    """Tests the BaseStorage.MakeMountCommands function on a Overlay storage."""
    container_obj = self.explorer_object.GetContainer(
        '5dc287aa80b460652a5584e80a5c8c1233b0c0691972d75424cf5250b917600a')
    commands = container_obj.storage_object.MakeMountCommands(
        container_obj, '/mnt')
    commands = [' '.join(cmd) for cmd in commands]
    expected_commands = [(
        '/bin/mount -t overlay overlay -o ro,lowerdir='
        'test_data/docker/overlay/974e2b994f9db74e1ddd6fc546843bc65920e786612'
        'a388f25685acf84b3fed1/upper:'
        'test_data/docker/overlay/a94d714512251b0d8a9bfaacb832e0c6cb70f71cb71'
        '976cca7a528a429336aae/root '
        '/mnt')]
    self.assertEqual(expected_commands, commands)

  def testGetHistory(self):
    """Tests the BaseStorage.GetHistory function on a Overlay storage."""
    self.maxDiff = None
    container_obj = self.explorer_object.GetContainer(
        '5dc287aa80b460652a5584e80a5c8c1233b0c0691972d75424cf5250b917600a')
    expected = {
        'sha256:'
        '5b0d59026729b68570d99bc4f3f7c31a2e4f2a5736435641565d93e7c25bd2c3':
        {
            'created_at': '2018-01-24T04:29:35.590938',
            'container_cmd': '/bin/sh -c #(nop)  CMD ["sh"]',
            'size': 0
        }
    }
    self.assertEqual(expected, container_obj.GetHistory())

  def testGetFullContainerID(self):
    """Tests the DockerExplorerTool._GetFullContainerID function on Overlay."""
    self.assertEqual(
        '5dc287aa80b460652a5584e80a5c8c1233b0c0691972d75424cf5250b917600a',
        self.explorer_object._GetFullContainerID('5dc287aa80'))

    with self.assertRaises(Exception) as err:
      self.explorer_object._GetFullContainerID('4')
    self.assertEqual(
        'Too many container IDs starting with "4": '
        '42e8679f78d6ea623391cdbcb928740ed804f928bd94f94e1d98687f34c48311, '
        '4ad09bee61dcc675bf41085dbf38c31426a7ed6666fdd47521bfb8f5e67a7e6d',
        err.exception.message)

    with self.assertRaises(Exception) as err:
      self.explorer_object._GetFullContainerID('xx')
    self.assertEqual(
        'Could not find any container ID starting with "xx"',
        err.exception.message)


class TestOverlay2Storage(DockerTestCase):
  """Tests methods in the Overlay2Storage object."""

  @classmethod
  def setUpClass(cls):
    cls._setup('overlay2', storage.Overlay2Storage)

  def testGetAllContainers(self):
    """Tests the GetAllContainers function on a Overlay2 storage."""
    containers_list = self.explorer_object.GetAllContainers()
    containers_list = sorted(containers_list, key=lambda ci: ci.name)
    self.assertEqual(5, len(containers_list))

    container_obj = containers_list[0]

    self.assertEqual('/festive_perlman', container_obj.name)
    self.assertEqual('2018-05-16T10:51:39.271019533Z',
                     container_obj.creation_timestamp)
    self.assertEqual('busybox', container_obj.config_image_name)
    self.assertTrue(container_obj.running)

    self.assertEqual(
        '8e8b7f23eb7cbd4dfe7e91646ddd0e0f524218e25d50113559f078dfb2690206',
        container_obj.container_id)

  def testGetOrderedLayers(self):
    """Tests the BaseStorage.GetOrderedLayers function on a Overlay2 storage."""
    container_obj = self.explorer_object.GetContainer(
        '8e8b7f23eb7cbd4dfe7e91646ddd0e0f524218e25d50113559f078dfb2690206')
    layers = container_obj.GetOrderedLayers()
    self.assertEqual(1, len(layers))
    self.assertEqual(
        'sha256:'
        '8ac48589692a53a9b8c2d1ceaa6b402665aa7fe667ba51ccc03002300856d8c7',
        layers[0])

  def testGetRunningContainersList(self):
    """Tests the BaseStorage.GetContainersList function on Overlay2 storage."""
    running_containers = self.explorer_object.GetContainersList(
        only_running=True)
    running_containers = sorted(
        running_containers, key=lambda ci: ci.container_id)
    self.assertEqual(1, len(running_containers))
    container_obj = running_containers[0]
    self.assertEqual('/festive_perlman', container_obj.name)
    self.assertEqual(
        '2018-05-16T10:51:39.271019533Z', container_obj.creation_timestamp)
    self.assertEqual('busybox', container_obj.config_image_name)

    self.assertTrue(container_obj.running)

  def testGetContainersJson(self):
    """Tests the GetContainersJson function on a Overlay2 storage."""
    result = self.explorer_object.GetContainersJson(only_running=True)
    expected = [
        {'image_id':
         '8ac48589692a53a9b8c2d1ceaa6b402665aa7fe667ba51ccc03002300856d8c7',
         'container_id':
         '8e8b7f23eb7cbd4dfe7e91646ddd0e0f524218e25d50113559f078dfb2690206',
         'mount_id':
         '92fd3b3e7d6101bb701743c9518c45b0d036b898c8a3d7cae84e1a06e6829b53',
         'start_date': '2018-05-16T10:51:39.625989',
         'image_name': 'busybox'}
    ]
    self.assertEqual(expected, result)

  def testGetLayerInfo(self):
    """Tests the BaseStorage.GetLayerInfo function on a Overlay2 storage."""
    container_obj = self.explorer_object.GetContainer(
        '8e8b7f23eb7cbd4dfe7e91646ddd0e0f524218e25d50113559f078dfb2690206')
    layer_info = container_obj.GetLayerInfo(
        'sha256:'
        '8ac48589692a53a9b8c2d1ceaa6b402665aa7fe667ba51ccc03002300856d8c7')
    self.assertEqual('2018-04-05T10:41:28.876407948Z', layer_info['created'])
    self.assertEqual(['/bin/sh', '-c', '#(nop) ', 'CMD ["sh"]'],
                     layer_info['container_config']['Cmd'])

  def testGetRepositoriesString(self):
    """Tests GetRepositoriesString() on a Overlay2 storage."""
    result_string = self.explorer_object.GetRepositoriesString()
    self.maxDiff = None
    expected_string = (
        '[\n'
        '    {\n'
        '        "Repositories": {}, \n'
        '        "path": "test_data/docker/image/overlay/repositories.json"\n'
        '    }, \n'
        '    {\n'
        '        "Repositories": {\n'
        '            "busybox": {\n'
        '                "busybox:latest": "sha256:'
        '8ac48589692a53a9b8c2d1ceaa6b402665aa7fe667ba51ccc03002300856d8c7", \n'
        '                "busybox@sha256:'
        '58ac43b2cc92c687a32c8be6278e50a063579655fe3090125dcb2af0ff9e1a64": '
        '"sha256:'
        '8ac48589692a53a9b8c2d1ceaa6b402665aa7fe667ba51ccc03002300856d8c7"\n'
        '            }\n'
        '        }, \n'
        '        "path": "test_data/docker/image/overlay2/repositories.json"\n'
        '    }\n'
        ']\n'
    )
    self.assertEqual(expected_string, result_string)

  def testMakeMountCommands(self):
    """Tests the BaseStorage.MakeMountCommands function on Overlay2 storage."""
    self.maxDiff = None
    container_obj = self.explorer_object.GetContainer(
        '8e8b7f23eb7cbd4dfe7e91646ddd0e0f524218e25d50113559f078dfb2690206')
    commands = container_obj.storage_object.MakeMountCommands(
        container_obj, '/mnt')
    commands = [' '.join(cmd) for cmd in commands]
    expected_commands = [(
        '/bin/mount -t overlay overlay -o ro,lowerdir='
        'test_data/docker/overlay2/'
        '92fd3b3e7d6101bb701743c9518c45b0d036b898c8a3d7cae84e1a06e6829b53/diff:'
        'test_data/docker/overlay2/l/OTFSLJCXWCECIG6FVNGRTWUZ7D:'
        'test_data/docker/overlay2/l/CH5A7XWSBP2DUPV7V47B7DOOGY /mnt'
        )]
    self.assertEqual(expected_commands, commands)

  def testGetHistory(self):
    """Tests the BaseStorage.GetHistory function on a Overlay2 storage."""
    self.maxDiff = None
    container_obj = self.explorer_object.GetContainer(
        '8e8b7f23eb7cbd4dfe7e91646ddd0e0f524218e25d50113559f078dfb2690206')
    expected = {
        'sha256:'
        '8ac48589692a53a9b8c2d1ceaa6b402665aa7fe667ba51ccc03002300856d8c7': {
            'created_at': '2018-04-05T10:41:28.876407',
            'container_cmd': '/bin/sh -c #(nop)  CMD ["sh"]',
            'size': 0
        }
    }
    self.assertEqual(expected, container_obj.GetHistory(container_obj))

  def testGetFullContainerID(self):
    """Tests the DockerExplorerTool._GetFullContainerID function on Overlay2."""
    self.assertEqual(
        '61ba4e6c012c782186c649466157e05adfd7caa5b551432de51043893cae5353',
        self.explorer_object._GetFullContainerID('61ba4e6c012c782'))

    with self.assertRaises(Exception) as err:
      self.explorer_object._GetFullContainerID('')
    self.assertEqual(
        'Too many container IDs starting with "": '
        '10acac0b3466813c9e1f85e2aa7d06298e51fbfe86bbcb6b7a19dd33d3798f6a, '
        '61ba4e6c012c782186c649466157e05adfd7caa5b551432de51043893cae5353, '
        '8e8b7f23eb7cbd4dfe7e91646ddd0e0f524218e25d50113559f078dfb2690206, '
        '9949fa153b778e39d6cab0a4e0ba60fa34a13fedb1f256d613a2f88c0c98408a, '
        'f83f963c67cbd36055f690fc988c1e42be06c1253e80113d1d516778c06b2841',
        err.exception.message)

    with self.assertRaises(Exception) as err:
      self.explorer_object._GetFullContainerID('xx')
    self.assertEqual(
        'Could not find any container ID starting with "xx"',
        err.exception.message)


del DockerTestCase

if __name__ == '__main__':
  unittest.main()
