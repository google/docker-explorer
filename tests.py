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

from docker_explorer import de
from docker_explorer import errors

from docker_explorer.lib import storage
from docker_explorer.lib import utils


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
    test_json = json.dumps(test_dict)
    expected_string = ('{\n    "test": [\n        {\n            "dict1": {\n'
                       '                "key1": "val1"\n            }, \n'
                       '            "dict2": null\n        }\n    ]\n}\n')
    self.assertEqual(expected_string, utils.PrettyPrintJSON(test_json))


class TestDEMain(unittest.TestCase):
  """Tests DockerExplorer object methods."""

  def testParseArguments(self):
    """Tests the DockerExplorer.ParseArguments function."""
    de_object = de.DockerExplorer()

    prog = sys.argv[0]

    expected_docker_root = os.path.join('test_data', 'docker')

    args = [prog, '-r', expected_docker_root, 'list', 'repositories']
    sys.argv = args

    options = de_object.ParseArguments()
    usage_string = de_object._argument_parser.format_usage()
    expected_usage = '[-h] [-r DOCKER_DIRECTORY] {mount,list,history} ...\n'
    self.assertTrue(expected_usage in usage_string)

    de_object.ParseOptions(options)
    self.assertEqual(expected_docker_root, options.docker_directory)

  def testDetectStorageFail(self):
    """Tests that the DockerExplorer.DetectStorage function fails on
    Docker directory."""
    de_object = de.DockerExplorer()
    de_object.docker_directory = 'this_dir_shouldnt_exist'

    expected_error_message = (
        'this_dir_shouldnt_exist is not a Docker directory\n'
        'Please specify the Docker\'s directory path.\n'
        'hint: de.py -r /var/lib/docker')

    with self.assertRaises(errors.BadStorageException) as err:
      de_object._SetDockerDirectory('this_dir_shouldnt_exist')
    self.assertEqual(expected_error_message, err.exception.message)


class DockerTestCase(unittest.TestCase):
  """Base class for tests of different Storage implementations."""

  @classmethod
  def tearDownClass(cls):
    shutil.rmtree(os.path.join('test_data', 'docker'))

  @classmethod
  def _setup(cls, driver, driver_class):
    """Internal method to set up the TestCase on a specific storage."""
    cls.driver = driver
    docker_directory_path = os.path.join('test_data', 'docker')
    if not os.path.isdir(docker_directory_path):
      docker_tar = os.path.join('test_data', cls.driver+'.tgz')
      tar = tarfile.open(docker_tar, 'r:gz')
      tar.extractall('test_data')
      tar.close()
    cls.de_object = de.DockerExplorer()
    cls.de_object._SetDockerDirectory(docker_directory_path)

    cls.driver_class = driver_class

  def testDetectStorage(self):
    """Tests the DockerExplorer.DetectStorage function."""
    for container_obj in self.de_object.GetAllContainers():
      self.assertIsNotNone(container_obj.storage_object)
      self.assertEqual(container_obj.storage_name, self.driver)
      self.assertIsInstance(container_obj.storage_object, self.driver_class)

      self.assertEqual(2, container_obj.docker_version)
      self.assertEqual(
          'config.v2.json', container_obj.container_config_filename)


class TestAufsStorage(DockerTestCase):
  """Tests methods in the BaseStorage object."""

  @classmethod
  def setUpClass(cls):
    cls._setup('aufs', storage.AufsStorage)

  def testGetAllContainers(self):
    """Tests the GetAllContainers function on a AuFS storage."""
    containers_list = self.de_object.GetAllContainers()
    containers_list = sorted(containers_list, key=lambda ci: ci.name)
    self.assertEqual(7, len(containers_list))

    container_obj = containers_list[1]

    self.assertEqual('/dreamy_snyder', container_obj.name)
    self.assertEqual('2017-02-13T16:45:05.629904159Z',
                     container_obj.creation_timestamp)
    self.assertEqual('busybox', container_obj.config_image_name)
    self.assertTrue(container_obj.running)

    expected_container_id = (
        '7b02fb3e8a665a63e32b909af5babb7d6ba0b64e10003b2d9534c7d5f2af8966')
    self.assertEqual(expected_container_id, container_obj.container_id)

  def testGetOrderedLayers(self):
    """Tests the BaseStorage.GetOrderedLayers function on a AUFS storage."""
    container_id = (
        '7b02fb3e8a665a63e32b909af5babb7d6ba0b64e10003b2d9534c7d5f2af8966')
    container_obj = self.de_object.GetContainer(container_id)
    layers = container_obj.GetOrderedLayers()
    self.assertEqual(1, len(layers))
    self.assertEqual(
        'sha256:'
        '7968321274dc6b6171697c33df7815310468e694ac5be0ec03ff053bb135e768',
        layers[0])

  def testGetRunningContainersList(self):
    """Tests the BaseStorage.GetContainersList function on a AUFS storage."""
    running_containers = self.de_object.GetContainersList(only_running=True)
    running_containers = sorted(
        running_containers, key=lambda ci: ci.container_id)
    self.assertEqual(1, len(running_containers))
    container = running_containers[0]
    self.assertEqual('/dreamy_snyder', container.name)
    self.assertEqual(
        '2017-02-13T16:45:05.629904159Z', container.creation_timestamp)
    self.assertEqual('busybox', container.config_image_name)
    self.assertTrue(container.running)

  def testGetContainersString(self):
    """Tests the GetContainersString function on a AUFS storage."""
    result_string = self.de_object.GetContainersString(only_running=True)
    expected_string = (
        'Container id: '
        '7b02fb3e8a665a63e32b909af5babb7d6ba0b64e10003b2d9534c7d5f2af8966 '
        '/ No Label\n'
        '\tStart date: 2017-02-13T16:45:05.785658\n'
        '\tImage ID: '
        '7968321274dc6b6171697c33df7815310468e694ac5be0ec03ff053bb135e768\n'
        '\tImage Name: busybox\n')
    self.assertEqual(expected_string, result_string)

  def testGetLayerInfo(self):
    """Tests the BaseStorage.GetLayerInfo function on a AUFS storage."""
    container_id = (
        '7b02fb3e8a665a63e32b909af5babb7d6ba0b64e10003b2d9534c7d5f2af8966')
    container_obj = self.de_object.GetContainer(container_id)
    layer_info = container_obj.GetLayerInfo(
        'sha256:'
        '7968321274dc6b6171697c33df7815310468e694ac5be0ec03ff053bb135e768')
    self.assertEqual('2017-01-13T22:13:54.401355854Z', layer_info['created'])
    self.assertEqual(['/bin/sh', '-c', '#(nop) ', 'CMD ["sh"]'],
                     layer_info['container_config']['Cmd'])

  def testGetRepositoriesString(self):
    """Tests BaseStorage.GetRepositoriesString() on a AUFS storage."""
    self.maxDiff = None
    result_string = self.de_object.GetRepositoriesString()
    expected_string = (
        'Listing repositories from file '
        'test_data/docker/image/aufs/repositories.json\n{\n'
        '    "Repositories": {\n'
        '        "busybox": {\n'
        '            "busybox:latest": '
        '"sha256:7968321274dc6b6171697c33df7815310468e694ac5be0ec03ff053bb135e7'
        '68"\n'
        '        }\n'
        '    }\n'
        '}\n')
    self.assertEqual(expected_string, result_string)

  def testMakeMountCommands(self):
    """Tests the BaseStorage.MakeMountCommands function on a AUFS storage."""
    container_id = (
        '7b02fb3e8a665a63e32b909af5babb7d6ba0b64e10003b2d9534c7d5f2af8966')
    container_obj = self.de_object.GetContainer(container_id)
    commands = container_obj.storage_object.MakeMountCommands(
        container_obj, '/mnt')
    expected_commands = [
        ('mount -t aufs -o ro,br=test_data/docker/aufs/diff/test_data/docker/'
         'aufs/diff/'
         'b16a494082bba0091e572b58ff80af1b7b5d28737a3eedbe01e73cd7f4e01d23'
         '=ro+wh none /mnt'),
        ('mount -t aufs -o ro,remount,append:test_data/docker/aufs/diff/'
         'b16a494082bba0091e572b58ff80af1b7b5d28737a3eedbe01e73cd7f4e01d23'
         '-init=ro+wh none /mnt'),
        ('mount -t aufs -o ro,remount,append:test_data/docker/aufs/diff/'
         'd1c54c46d331de21587a16397e8bd95bdbb1015e1a04797c76de128107da83ae'
         '=ro+wh none /mnt'),
        ('mount --bind -o ro {0:s}/docker/volumes/'
         '28297de547b5473a9aff90aaab45ed108ebf019981b40c3c35c226f54c13ac0d/'
         '_data /mnt/var/jenkins_home').format(os.path.abspath('test_data'))
    ]
    self.assertEqual(expected_commands, commands)

  def testGetHistory(self):
    """Tests the BaseStorage.GetHistory function on a AUFS storage."""
    self.maxDiff = None
    container_id = (
        '7b02fb3e8a665a63e32b909af5babb7d6ba0b64e10003b2d9534c7d5f2af8966')
    container_obj = self.de_object.GetContainer(container_id)
    expected_string = (
        '-------------------------------------------------------\n'
        'sha256:'
        '7968321274dc6b6171697c33df7815310468e694ac5be0ec03ff053bb135e768\n'
        '\tsize : 0\tcreated at : 2017-01-13T22:13:54.401355\t'
        'with command : /bin/sh -c #(nop)  CMD ["sh"]')
    self.assertEqual(expected_string, container_obj.GetHistory())

  def testGetFullContainerID(self):
    """Tests the DockerExplorer._GetFullContainerID function on AuFS."""
    self.assertEqual(
        '2cc4b0d9c1dfdf71099c5e9a109e6a0fe286152a5396bd1850689478e8f70625',
        self.de_object._GetFullContainerID('2cc4b0d'))

    with self.assertRaises(Exception) as err:
      self.de_object._GetFullContainerID('')
    self.assertEqual(
        'Too many containers whose ID starts with "" (7)',
        err.exception.message)

    with self.assertRaises(Exception) as err:
      self.de_object._GetFullContainerID('xx')
    self.assertEqual(
        'Could not find any container whose ID starts with "xx"',
        err.exception.message)


class TestOverlayStorage(DockerTestCase):
  """Tests methods in the OverlayStorage object."""

  @classmethod
  def setUpClass(cls):
    cls._setup('overlay', storage.OverlayStorage)

  def testGetAllContainers(self):
    """Tests the GetAllContainers function on a Overlay storage."""
    containers_list = self.de_object.GetAllContainers()
    containers_list = sorted(containers_list, key=lambda ci: ci.name)
    self.assertEqual(6, len(containers_list))

    container_obj = containers_list[0]

    self.assertEqual('/elastic_booth', container_obj.name)
    self.assertEqual('2018-01-26T14:55:56.280943771Z',
                     container_obj.creation_timestamp)
    self.assertEqual('busybox:latest', container_obj.config_image_name)
    self.assertTrue(container_obj.running)

    expected_container_id = (
        '5dc287aa80b460652a5584e80a5c8c1233b0c0691972d75424cf5250b917600a')
    self.assertEqual(expected_container_id, container_obj.container_id)

  def testGetOrderedLayers(self):
    """Tests the BaseStorage.GetOrderedLayers function on a Overlay storage."""
    container_id = (
        '5dc287aa80b460652a5584e80a5c8c1233b0c0691972d75424cf5250b917600a')
    container_obj = self.de_object.GetContainer(container_id)
    layers = container_obj.GetOrderedLayers()
    self.assertEqual(1, len(layers))
    self.assertEqual(
        'sha256:'
        '5b0d59026729b68570d99bc4f3f7c31a2e4f2a5736435641565d93e7c25bd2c3',
        layers[0])

  def testGetRunningContainersList(self):
    """Tests the BaseStorage.GetContainersList function on a Overlay storage."""
    running_containers = self.de_object.GetContainersList(only_running=True)
    running_containers = sorted(
        running_containers, key=lambda ci: ci.container_id)
    self.assertEqual(1, len(running_containers))
    container = running_containers[0]
    self.assertEqual('/elastic_booth', container.name)
    self.assertEqual(
        '2018-01-26T14:55:56.280943771Z', container.creation_timestamp)
    self.assertEqual('busybox:latest', container.config_image_name)

    self.assertTrue(container.running)

  def testGetContainersString(self):
    """Tests the GetContainersString function on a Overlay storage."""
    result_string = self.de_object.GetContainersString(only_running=True)
    expected_string = (
        'Container id: '
        '5dc287aa80b460652a5584e80a5c8c1233b0c0691972d75424cf5250b917600a '
        '/ No Label\n'
        '\tStart date: 2018-01-26T14:55:56.574924\n'
        '\tImage ID: '
        '5b0d59026729b68570d99bc4f3f7c31a2e4f2a5736435641565d93e7c25bd2c3\n'
        '\tImage Name: busybox:latest\n')
    self.assertEqual(expected_string, result_string)

  def testGetLayerInfo(self):
    """Tests the BaseStorage.GetLayerInfo function on a Overlay storage."""
    container_id = (
        '5dc287aa80b460652a5584e80a5c8c1233b0c0691972d75424cf5250b917600a')
    container_obj = self.de_object.GetContainer(container_id)
    layer_info = container_obj.GetLayerInfo(
        'sha256:'
        '5b0d59026729b68570d99bc4f3f7c31a2e4f2a5736435641565d93e7c25bd2c3')
    self.assertEqual('2018-01-24T04:29:35.590938514Z', layer_info['created'])
    self.assertEqual(['/bin/sh', '-c', '#(nop) ', 'CMD ["sh"]'],
                     layer_info['container_config']['Cmd'])

  def testGetRepositoriesString(self):
    """Tests BaseStorage.GetRepositoriesString() on a Overlay storage."""
    result_string = self.de_object.GetRepositoriesString()
    self.maxDiff = None
    expected_string = (
        'Listing repositories from file '
        'test_data/docker/image/overlay/repositories.json\n{\n'
        '    "Repositories": {\n'
        '        "busybox": {\n'
        '            "busybox:latest": "sha256:'
        '5b0d59026729b68570d99bc4f3f7c31a2e4f2a5736435641565d93e7c25bd2c3", \n'
        '            "busybox@sha256:1669a6aa7350e1cdd28f972ddad5aceba2912f589'
        'f19a090ac75b7083da748db": '
        '"sha256:5b0d59026729b68570d99bc4f3f7c31a2e4f2a5736435641565d93e7c25bd'
        '2c3"\n'
        '        }\n'
        '    }\n'
        '}\n')
    self.assertEqual(expected_string, result_string)

  def testMakeMountCommands(self):
    """Tests the BaseStorage.MakeMountCommands function on a Overlay storage."""
    container_id = (
        '5dc287aa80b460652a5584e80a5c8c1233b0c0691972d75424cf5250b917600a')
    container_obj = self.de_object.GetContainer(container_id)
    commands = container_obj.storage_object.MakeMountCommands(
        container_obj, '/mnt')
    expected_commands = [(
        'mount -t overlay overlay -o ro,lowerdir='
        '"test_data/docker/overlay/a94d714512251b0d8a9bfaacb832e0c6cb70f71cb71'
        '976cca7a528a429336aae/root":'
        '"test_data/docker/overlay/974e2b994f9db74e1ddd6fc546843bc65920e786612'
        'a388f25685acf84b3fed1/upper",'
        'workdir="test_data/docker/overlay/974e2b994f9db74e1ddd6fc546843bc6592'
        '0e786612a388f25685acf84b3fed1/work" "/mnt"')]
    self.assertEqual(expected_commands, commands)

  def testGetHistory(self):
    """Tests the BaseStorage.GetHistory function on a Overlay storage."""
    self.maxDiff = None
    container_id = (
        '5dc287aa80b460652a5584e80a5c8c1233b0c0691972d75424cf5250b917600a')
    container_obj = self.de_object.GetContainer(container_id)
    expected_string = (
        '-------------------------------------------------------\n'
        'sha256:'
        '5b0d59026729b68570d99bc4f3f7c31a2e4f2a5736435641565d93e7c25bd2c3\n'
        '\tsize : 0\tcreated at : 2018-01-24T04:29:35.590938\t'
        'with command : /bin/sh -c #(nop)  CMD ["sh"]')
    self.assertEqual(expected_string, container_obj.GetHistory())

  def testGetFullContainerID(self):
    """Tests the DockerExplorer._GetFullContainerID function on Overlay."""
    self.assertEqual(
        '5dc287aa80b460652a5584e80a5c8c1233b0c0691972d75424cf5250b917600a',
        self.de_object._GetFullContainerID('5dc287aa80'))

    with self.assertRaises(Exception) as err:
      self.de_object._GetFullContainerID('4')
    self.assertEqual(
        'Too many containers whose ID starts with "4" (2)',
        err.exception.message)

    with self.assertRaises(Exception) as err:
      self.de_object._GetFullContainerID('xx')
    self.assertEqual(
        'Could not find any container whose ID starts with "xx"',
        err.exception.message)


class TestOverlay2Storage(DockerTestCase):
  """Tests methods in the Overlay2Storage object."""

  @classmethod
  def setUpClass(cls):
    cls._setup('overlay2', storage.Overlay2Storage)

  def testGetAllContainers(self):
    """Tests the GetAllContainers function on a Overlay2 storage."""
    containers_list = self.de_object.GetAllContainers()
    containers_list = sorted(containers_list, key=lambda ci: ci.name)
    self.assertEqual(5, len(containers_list))

    container_obj = containers_list[0]

    self.assertEqual('/festive_perlman', container_obj.name)
    self.assertEqual('2018-05-16T10:51:39.271019533Z',
                     container_obj.creation_timestamp)
    self.assertEqual('busybox', container_obj.config_image_name)
    self.assertTrue(container_obj.running)

    expected_container_id = (
        '8e8b7f23eb7cbd4dfe7e91646ddd0e0f524218e25d50113559f078dfb2690206')
    self.assertEqual(expected_container_id, container_obj.container_id)

  def testGetOrderedLayers(self):
    """Tests the BaseStorage.GetOrderedLayers function on a Overlay2 storage."""
    container_id = (
        '8e8b7f23eb7cbd4dfe7e91646ddd0e0f524218e25d50113559f078dfb2690206')
    container_obj = self.de_object.GetContainer(container_id)
    layers = container_obj.GetOrderedLayers()
    self.assertEqual(1, len(layers))
    self.assertEqual(
        'sha256:'
        '8ac48589692a53a9b8c2d1ceaa6b402665aa7fe667ba51ccc03002300856d8c7',
        layers[0])

  def testGetRunningContainersList(self):
    """Tests the BaseStorage.GetContainersList function on Overlay2 storage."""
    running_containers = self.de_object.GetContainersList(only_running=True)
    running_containers = sorted(
        running_containers, key=lambda ci: ci.container_id)
    self.assertEqual(1, len(running_containers))
    container = running_containers[0]
    self.assertEqual('/festive_perlman', container.name)
    self.assertEqual(
        '2018-05-16T10:51:39.271019533Z', container.creation_timestamp)
    self.assertEqual('busybox', container.config_image_name)

    self.assertTrue(container.running)

  def testGetContainersString(self):
    """Tests the GetContainersString function on a Overlay2 storage."""
    result_string = self.de_object.GetContainersString(only_running=True)
    expected_string = (
        'Container id: '
        '8e8b7f23eb7cbd4dfe7e91646ddd0e0f524218e25d50113559f078dfb2690206 '
        '/ No Label\n'
        '\tStart date: 2018-05-16T10:51:39.625989\n'
        '\tImage ID: '
        '8ac48589692a53a9b8c2d1ceaa6b402665aa7fe667ba51ccc03002300856d8c7\n'
        '\tImage Name: busybox\n')
    self.assertEqual(expected_string, result_string)

  def testGetLayerInfo(self):
    """Tests the BaseStorage.GetLayerInfo function on a Overlay2 storage."""
    container_id = (
        '8e8b7f23eb7cbd4dfe7e91646ddd0e0f524218e25d50113559f078dfb2690206')
    container_obj = self.de_object.GetContainer(container_id)
    layer_info = container_obj.GetLayerInfo(
        'sha256:'
        '8ac48589692a53a9b8c2d1ceaa6b402665aa7fe667ba51ccc03002300856d8c7')
    self.assertEqual('2018-04-05T10:41:28.876407948Z', layer_info['created'])
    self.assertEqual(['/bin/sh', '-c', '#(nop) ', 'CMD ["sh"]'],
                     layer_info['container_config']['Cmd'])

  def testGetRepositoriesString(self):
    """Tests BaseStorage.GetRepositoriesString() on a Overlay2 storage."""
    result_string = self.de_object.GetRepositoriesString()
    self.maxDiff = None
    expected_string = (
        'Listing repositories from file '
        'test_data/docker/image/overlay/repositories.json\n'
        '{\n'
        '    "Repositories": {}\n'
        '}\n'
        'Listing repositories from file '
        'test_data/docker/image/overlay2/repositories.json\n{\n'
        '    "Repositories": {\n'
        '        "busybox": {\n'
        '            "busybox:latest": "sha256:'
        '8ac48589692a53a9b8c2d1ceaa6b402665aa7fe667ba51ccc03002300856d8c7", \n'
        '            "busybox@sha256:58ac43b2cc92c687a32c8be6278e50a063579655fe'
        '3090125dcb2af0ff9e1a64": '
        '"sha256:8ac48589692a53a9b8c2d1ceaa6b402665aa7fe667ba51ccc03002300856d8'
        'c7"\n'
        '        }\n'
        '    }\n'
        '}\n'

    )
    self.assertEqual(expected_string, result_string)

  def testMakeMountCommands(self):
    """Tests the BaseStorage.MakeMountCommands function on Overlay2 storage."""
    self.maxDiff = None
    container_id = (
        '8e8b7f23eb7cbd4dfe7e91646ddd0e0f524218e25d50113559f078dfb2690206')
    container_obj = self.de_object.GetContainer(container_id)
    commands = container_obj.storage_object.MakeMountCommands(
        container_obj, '/mnt')
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

  def testGetHistory(self):
    """Tests the BaseStorage.GetHistory function on a Overlay2 storage."""
    self.maxDiff = None
    container_id = (
        '8e8b7f23eb7cbd4dfe7e91646ddd0e0f524218e25d50113559f078dfb2690206')
    container_obj = self.de_object.GetContainer(container_id)
    expected_string = (
        '-------------------------------------------------------\n'
        'sha256:'
        '8ac48589692a53a9b8c2d1ceaa6b402665aa7fe667ba51ccc03002300856d8c7\n'
        '\tsize : 0\tcreated at : 2018-04-05T10:41:28.876407\t'
        'with command : /bin/sh -c #(nop)  CMD ["sh"]')
    self.assertEqual(expected_string, container_obj.GetHistory(container_obj))

  def testGetFullContainerID(self):
    """Tests the DockerExplorer._GetFullContainerID function on Overlay2."""
    self.assertEqual(
        '61ba4e6c012c782186c649466157e05adfd7caa5b551432de51043893cae5353',
        self.de_object._GetFullContainerID('61ba4e6c012c782'))

    with self.assertRaises(Exception) as err:
      self.de_object._GetFullContainerID('')
    self.assertEqual(
        'Too many containers whose ID starts with "" (5)',
        err.exception.message)

    with self.assertRaises(Exception) as err:
      self.de_object._GetFullContainerID('xx')
    self.assertEqual(
        'Could not find any container whose ID starts with "xx"',
        err.exception.message)


del DockerTestCase

if __name__ == '__main__':
  unittest.main()
