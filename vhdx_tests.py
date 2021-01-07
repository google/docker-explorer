# -*- coding: utf-8 -*-
# Copyright 2020 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Tests for the vhdx.py tool."""

import os
import sys
import shutil
import tarfile
import unittest
import unittest.mock
import tempfile
import hashlib

from tools.merge_vhdx import BATParams
from tools.merge_vhdx import SectorBitmapBATEntry
from tools.merge_vhdx import PayloadBlockBATEntry
from tools.merge_vhdx import BlockAllocationTable
from tools.merge_vhdx import VHDXDisk
from tools.merge_vhdx import MergeVHDXTool

# pylint: disable=protected-access

class BlockAllocationTableEntryTests(unittest.TestCase):
  """Tests for the BlockAllocationTableEntry subclasses"""

  def testSectorBitmapParse(self):
    """Tests SectorBitmapBATEntry parsing"""
    bat_entry = SectorBitmapBATEntry(b'\x06\x00\x10\x01\x00\x00\x00\x00')
    expected_state = 'SB_BLOCK_PRESENT'
    expected_offset = 0x1100000
    self.assertEqual(expected_state, bat_entry.state)
    self.assertEqual(expected_offset, bat_entry.offset)

  def testSectorBitmapParseStateInvalid(self):
    """Tests the appropriate error is raised for an invalid state"""
    with self.assertRaises(ValueError):
      _ = SectorBitmapBATEntry(b'\x05\x00\x10\x01\x00\x00\x00\x00')

  def testPayloadBlockParse(self):
    """Tests PayloadBlockBATEntry parsing"""
    bat_entry = PayloadBlockBATEntry(b'\x07\x00\x10\x01\x00\x00\x00\x00')
    expected_state = 'PAYLOAD_BLOCK_PARTIALLY_PRESENT'
    expected_offset = 0x1100000
    self.assertEqual(expected_state, bat_entry.state)
    self.assertEqual(expected_offset, bat_entry.offset)

  def testPayloadBlockParseStateInvalid(self):
    """Tests the appropriate error is raised for an invalid state"""
    with self.assertRaises(ValueError):
      _ = PayloadBlockBATEntry(b'\x05\x00\x10\x01\x00\x00\x00\x00')


class BlockAllocationTableTests(unittest.TestCase):
  """Tests for the BlockAllocationTable class"""

  def setUp(self):
    bat_bytes = b'\x07\x00\x10\x01\x00\x00\x00\x00'*10 +\
        b'\x06\x00\x10\x01\x00\x00\x00\x00'
    bat_params = BATParams(10, 11, 10, 1)
    self.bat_table = BlockAllocationTable(bat_bytes, bat_params)

  def testParseBATBytes(self):
    """Test that the correct number of BAT entries are parsed"""
    self.assertEqual(len(self.bat_table.payload_entries), 10)
    self.assertEqual(len(self.bat_table.sector_bitmap_entries), 1)

  def testParseBATBytesError(self):
    "Tests that a ValueError is raised on unexpected results"
    bat_bytes = b'\x07\x00\x10\x01\x00\x00\x00\x00'*10 +\
        b'\x06\x00\x10\x01\x00\x00\x00\x00'*2
    bat_params = BATParams(10, 11, 10, 1)
    with self.assertRaises(ValueError):
      self.bat_table = BlockAllocationTable(bat_bytes, bat_params)

  def testGetPayloadBatEntry(self):
    """Test GetPayloadBatEntry"""
    self.assertEqual('PAYLOAD_BLOCK_PARTIALLY_PRESENT',
        self.bat_table.GetPayloadBATEntry(0).state)

  def testGetSectorBitmapBATEntry(self):
    """Test GetSectorBitmapBATEntry"""
    self.assertEqual('SB_BLOCK_PRESENT',
        self.bat_table.GetSectorBitmapBATEntry(0).state)

class VHDXDiskTests(unittest.TestCase):
  """Tests for the VHDXDisk class"""

  @classmethod
  def tearDownClass(cls):
    shutil.rmtree(cls.vhdx_files_path)

  @classmethod
  def setUpClass(cls):
    cls.vhdx_files_path = os.path.join('test_data', 'vhdx_files')
    if not os.path.isdir(cls.vhdx_files_path):
      vhdx_tar = os.path.join('test_data', 'vhdx_files.tgz')
      tar = tarfile.open(vhdx_tar, 'r:gz')
      tar.extractall('test_data')
      tar.close()
    base_path = os.path.join(cls.vhdx_files_path, 'base.vhdx')
    diff_path = os.path.join(cls.vhdx_files_path, 'diff.vhdx')
    cls.base_disk = VHDXDisk(base_path)
    cls.diff_disk = VHDXDisk(diff_path, parent_disk=cls.base_disk)

  def testParseDiskParams(self):
    """Tests _ParseDiskParams and associated functions"""
    self.assertEqual(1024**2, self.base_disk.disk_params.block_size)
    self.assertEqual(512, self.base_disk.disk_params.logical_sector_size)
    self.assertEqual(False, self.base_disk.disk_params.has_parent)
    self.assertEqual(4*1024**2, self.base_disk.disk_params.virtual_disk_size)
    self.assertEqual(8192, self.base_disk.disk_params.sector_count)

  def testCalculateBATParams(self):
    """Tests for the _CalculateBATParams method"""
    self.assertEqual(4096, self.base_disk.bat_params.chunk_ratio)
    self.assertEqual(4, self.base_disk.bat_params.total_entries)
    self.assertEqual(4, self.base_disk.bat_params.payload_entries)
    self.assertEqual(1, self.base_disk.bat_params.sector_bitmap_entries)

  def testConvertBytesToBitmap(self):
    """Tests for the _ConvertBytesToBitmap method"""
    sb_bytes = b'\xf0\x0f'
    expected = [False]*4 + [True]*8 + [False]*4
    self.assertEqual(expected, self.diff_disk._ConvertBytesToBitmap(sb_bytes))

  def testGetSectorBitmapForBlock(self):
    """Tests for the _GetSectorBitmapForBlock method"""
    expected = [False]*72 + [True]*8 + [False]*8
    result = self.diff_disk._GetSectorBitmapForBlock(1)[:88]
    self.assertEqual(expected, result)

  def testReadSectorBaseDisk(self):
    """Test for the _GetSectorBitmapForBlock method for a base disk"""
    expected = b'\x33\xc0\x8e\xd0\xbc\x00\x7c\x8e'
    result = self.base_disk.ReadSector(0)[:8]
    self.assertEqual(expected, result)

  def testReadSectorDiffDisk(self):
    """Tests for the _GetSectorBitmapForBlock method for a diff disk"""
    expected = b'\x33\xc0\x8e\xd0\xbc\x00\x7c\x8e'
    result = self.diff_disk.ReadSector(0)[:8]
    self.assertEqual(expected, result)

  def testReadSectorBytes(self):
    """Tests for the _ReadSectorBytes method"""
    expected = b'\x33\xc0\x8e\xd0\xbc\x00\x7c\x8e'
    bat_entry = PayloadBlockBATEntry(b'\x06\x00\x40\x00\x00\x00\x00\x00')
    sector_in_block = 0
    result = self.base_disk._ReadSectorBytes(bat_entry, sector_in_block)[:8]
    self.assertEqual(expected, result)


class MergeVHDXToolTests(unittest.TestCase):
  """Tests for the MergeVHDXTool class"""

  @classmethod
  def tearDownClass(cls):
    shutil.rmtree(cls.vhdx_files_path)

  @classmethod
  def setUpClass(cls):
    cls.vhdx_files_path = os.path.join('test_data', 'vhdx_files')
    if not os.path.isdir(cls.vhdx_files_path):
      vhdx_tar = os.path.join('test_data', 'vhdx_files.tgz')
      tar = tarfile.open(vhdx_tar, 'r:gz')
      tar.extractall('test_data')
      tar.close()
    cls.base_path = os.path.join(cls.vhdx_files_path, 'base.vhdx')
    cls.diff_path = os.path.join(cls.vhdx_files_path, 'diff.vhdx')

  def testMain(self):
    """Tests the main method of MergeVHDXTool"""
    expected_hash = (
        'a9717baccc52410c8c1ecb3ad096ccdfb842b4a48068b0d86f4191efa3985693')
    tool_object = MergeVHDXTool()
    out_file = tempfile.mktemp()
    prog = sys.argv[0]
    sys.argv = [prog, '-p', self.base_path, '-c', self.diff_path, '-o',
        out_file, '-y']

    tool_object.Main()
    result_hash = hashlib.sha256()
    with open(out_file, "rb") as fd:
      result_hash.update(fd.read())
    os.remove(out_file)

    self.assertEqual(expected_hash, result_hash.hexdigest())


if __name__ == '__main__':
  unittest.main()
