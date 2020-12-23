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

import unittest
import unittest.mock

from tools.merge_vhdx import SectorBitmapBATEntry
from tools.merge_vhdx import PayloadBlockBATEntry
from tools.merge_vhdx import BlockAllocationTable
from tools.merge_vhdx import VHDXDisk
from tools.merge_vhdx import MergeVHDXTool


class BlockAllocationTableEntryTests(unittest.TestCase):
  """Tests for the SectorBitmapBATEntry class"""

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


if __name__ == '__main__':
  unittest.main()
