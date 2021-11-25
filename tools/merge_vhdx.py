#!/usr/bin/python3
# -*- coding: utf-8 -*-
# Copyright 2020 Google Inc.
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
"""Merge VHDX.

A tool to merge differencing VHDX files.
"""

import argparse
import sys
import uuid
import struct
import math
import logging
from collections import namedtuple

logger = logging.getLogger('merge_vhdx')

REGION_HEADER_OFFSET = 192*1024
LEN_BAT_ENTRY = 8
BAT_ENTRY_STATE_BITMASK = 0b00000111
BAT_ENTRY_OFFSET_LEAD_BYTE_BITMASK = 0b11110000

GUID_BAT = '2dc27766-f623-4200-9d64-115e9bfd4a08'
GUID_METADATA = '8b7ca206-4790-4b9a-b8fe-575f050f886e'
GUID_FILE_PARAM = 'caa16737-fa36-4d43-b3b6-33f0aa44e76b'
GUID_DISK_SIZE = '2fa54224-cd1b-4876-b211-5dbed83bf4b8'
GUID_DISK_ID = 'beca12ab-b2e6-4523-93ef-c309e000c746'
GUID_LOGICAL_SECTOR_SIZE = '8141bf1d-a96f-4709-ba47-f233a8faab5f'
GUID_PHYSICAL_SECTOR_SIZE = 'cda348c7-445d-4471-9cc9-e9885251c556'
GUID_PARENT_LOCATOR = 'a8d35f2d-b30b-454d-abf7-d3d84834ab0c'

SB_BLOCK_STATES = [
  'SB_BLOCK_NOT_PRESENT',
  'INVALID',
  'INVALID',
  'INVALID',
  'INVALID',
  'INVALID',
  'SB_BLOCK_PRESENT'
]

PAYLOAD_BLOCK_STATES = [
  'PAYLOAD_BLOCK_NOT_PRESENT',
  'PAYLOAD_BLOCK_UNDEFINED',
  'PAYLOAD_BLOCK_ZERO',
  'PAYLOAD_BLOCK_UNMAPPED',
  'INVALID',
  'INVALID',
  'PAYLOAD_BLOCK_FULLY_PRESENT',
  'PAYLOAD_BLOCK_PARTIALLY_PRESENT'
]


BATParams = namedtuple('BATParams', ['chunk_ratio', 'total_entries',
    'payload_entries', 'sector_bitmap_entries'])


DiskParams = namedtuple('DiskParams', ['block_size', 'logical_sector_size',
    'virtual_disk_size', 'has_parent', 'sector_count'])


class BlockAllocationTableEntry:
  """Represents a VHDX block allocation table entry.

  Attributes:
    state (str): the state of BAT entry
    offset (int): the offset of the block the BAT entry references
  """

  def __init__(self, bat_bytes):
    """Initialises a BlockAllocationTableEntry

    Args:
      bat_bytes (bytes): a bytes object representing the BAT entry
    """
    self.state = self._parseState(bat_bytes)
    self.offset = self._parseOffset(bat_bytes)

  def _parseState(self, bat_bytes):
    """Parses BAT state

    Args:
      bat_bytes (bytes): a bytes object representing the BAT entry

    Raises:
      NotImplementedError: if called on the base class
    """
    raise NotImplementedError

  def _parseOffset(self, bat_bytes):
    """Parses BAT offset

    Args:
      bat_bytes (bytes): a bytes object with length of 8 representing the entry
    Returns:
      int: the offset.
    """
    # Offset is a 44 bit wide field, so use a bitmask for lead 4 bits.
    offset_lead_byte = bat_bytes[2] & BAT_ENTRY_OFFSET_LEAD_BYTE_BITMASK
    offset_other_bytes = bat_bytes[3:]
    # Pad with zeroes for ease of parsing
    offset_bytes = b'\x00'*2 + bytes([offset_lead_byte]) + offset_other_bytes
    return struct.unpack("<Q", offset_bytes)[0]


class SectorBitmapBATEntry(BlockAllocationTableEntry):
  """Represents a sector bitmap block entry.

  Attributes:
    state (str): the state of BAT entry
    offset (int): the offset of the block the BAT entry references
  """

  def _parseState(self, bat_bytes):
    """Parses BAT state

    Args:
      bat_bytes (bytes): a bytes object representing the BAT entry

    Returns:
      str: the parsed state.

    Raises:
      ValueError: if the state field is invalid
    """
    state_int = bat_bytes[0] & BAT_ENTRY_STATE_BITMASK
    state = SB_BLOCK_STATES[state_int]
    if state == 'INVALID':
      raise ValueError(f'Invalid state {state_int} for sector bitmap entry')
    return state


class PayloadBlockBATEntry(BlockAllocationTableEntry):
  """Represents a payload block BAT entry.

  Attributes:
    state (str): the state of BAT entry
    offset (int): the offset of the block the BAT entry references
  """

  def _parseState(self, bat_bytes):
    """Parses BAT state

    Args:
      bat_bytes (bytes): a bytes object representing the BAT entry

    Returns:
      str: the parsed state.

    Raises:
      ValueError: if the state field is invalid
    """
    state_int = bat_bytes[0] & BAT_ENTRY_STATE_BITMASK
    state = PAYLOAD_BLOCK_STATES[state_int]
    if state == 'INVALID':
      raise ValueError(f'Invalid state {state_int} for payload block entry')
    return state


class BlockAllocationTable:
  """Represents a VHDX block allocation table.

  Parses the payload and sector bitmap entries into two separate lists.
  Indexes into the payload entries list represent block numbers while
  indexes into the sector bitmap entries list represent chunks numbers.

  Attributes:
    payload_entries (list(PayloadBlockBitmapBATEntry)): a list of BAT payload
      entries
    sector_bitmap_entries (list(SectorBitmapBATEntry)): a list of sector
      bitmap entries
  """
  def __init__(self, bat_bytes, bat_params):
    """Initialises a BlockAllocationTable.

    Args:
      bat_bytes (bytes): raw bytes representing the bat table
      bat_params (BATParams): BAT details for error checking
    """
    parsed_bat = self._ParseBATBytes(bat_bytes, bat_params)
    self.payload_entries = parsed_bat[0]
    self.sector_bitmap_entries = parsed_bat[1]

  def _ParseBATBytes(self, bat_bytes, bat_params):
    """Parses the block allocation table

    Args:
      bat_bytes (bytes): the raw bytes representing a BAT table
      bat_params (BatParams): the parsed BAT params

    Returns:
      tuple(list, list): the parsed block allocation table

    Raises:
      ValueError: if the expected number of entries aren't parsed
    """
    payload_entries = []
    sector_bitmap_entries = []
    progress_in_chunk = 0

    for idx in range(0, len(bat_bytes), LEN_BAT_ENTRY):
      if progress_in_chunk == bat_params.chunk_ratio:
        # Means this entry is for a sector bitmap block
        parsed_entry = SectorBitmapBATEntry(bat_bytes[idx:idx+8])
        sector_bitmap_entries.append(parsed_entry)
        progress_in_chunk = 0 # Sector bitmap entry means end of this chunk
      else:
        parsed_entry = PayloadBlockBATEntry(bat_bytes[idx:idx+8])
        payload_entries.append(parsed_entry)
        progress_in_chunk += 1

    total_entries = len(payload_entries) + len(sector_bitmap_entries)
    if total_entries != bat_params.total_entries:
      raise ValueError(
          'Incorrect number of entries parsed expected '
          f'{bat_params.total_entries} parsed {total_entries}')

    logger.debug(
        f'Parsed {len(payload_entries)} payload entries and '
        f'{len(sector_bitmap_entries)} sector bitmap entries')
    return (payload_entries, sector_bitmap_entries)

  def GetPayloadBATEntry(self, block_number):
    """Returns a data block entry for for a given block number

    Args:
      block_number (int): the block number to retrieve an entry for

    Returns:
      PayloadBlockBitmapBATEntry: the PayloadBlockBitmapBATEntry object.
    """
    return self.payload_entries[block_number]

  def GetSectorBitmapBATEntry(self, chunk_number):
    """Returns a sector bitmap block for for a given chunk number

    Args:
      chunk_number (int): the chunk number to retrieve an entry for

    Returns:
      SectorBitmapBATEntry: the SectorBitmapBATEntry object.
    """
    return self.sector_bitmap_entries[chunk_number]


class VHDXDisk:
  """Represents a VHDX virtual disk.

  The VHDX format is documented by Microsoft as an open specification at:
  https://docs.microsoft.com/en-us/openspecs/windows_protocols/ms-vhdx

  Attributes:
    vhdx_name (str): the on-disk name of the VHDX file
    vhdx_fd (file): the open VHDX file
    parent_disk (VHDXDisk): the parent disk if this is a differencing disk
    region_table (dict): a parsed region table with GUIDs as keys
    metadata_table (dict): a parsed metadata table with GUIDs as keys
    disk_params (DiskParams): the parsed disk params
    bat_params (BATParams): the parsed BAT params
    bat_table (BlockAllocationTable): the parsed block allocation table
  """

  def __init__(self, vhdx_name, parent_disk=None):
    """Initialises a VHDXDisk

    Args:
      vhdx_name (str): the name of the target VHDX file
      parent_disk (VHDXDisk) Optional: the parent disk if this is a child disk
    """
    self.vhdx_name = vhdx_name
    self.vhdx_fd = open(vhdx_name, 'rb')  #pylint: disable=consider-using-with
    self.parent_disk = parent_disk
    self.region_table = self._ParseRegionTable()
    self.metadata_table = self._ParseMetadataTable()
    self.disk_params = self._ParseDiskParams()
    self.bat_params = self._CalculateBATParams()
    self.bat_table = self._ParseBAT()

  def __del__(self):
    """Explicitly lose the vhdx fd on deletion"""
    self.vhdx_fd.close()

  def _ParseRegionTable(self):
    """Parses a region table from a VHDX disk

    Returns:
      list(tuple): A list of VHDX regions represented as UUID/offset
        tuples
    """
    self.vhdx_fd.seek(REGION_HEADER_OFFSET)
    self.vhdx_fd.seek(8, 1) # Region table signature + checksum
    entry_count = struct.unpack('<I', self.vhdx_fd.read(4))[0]
    self.vhdx_fd.seek(4, 1) # Res bytes
    region_table = {}
    for _ in range(0, entry_count):
      guid = str(uuid.UUID(bytes_le=self.vhdx_fd.read(16)))
      offset = struct.unpack('<Q', self.vhdx_fd.read(8))[0]
      self.vhdx_fd.seek(8, 1) # Region length + required indicator
      region_table[guid] = offset
    return region_table

  def _ParseMetadataTable(self):
    """Parses a metadata table from a VHDX disk

    Returns:
      list(tuple): A list of metadata items represented as UUID/offset
        tuples
    """
    self.vhdx_fd.seek(self.region_table[GUID_METADATA])
    self.vhdx_fd.seek(10, 1) # Metadata table signature + res bytes
    entry_count = struct.unpack('<H', self.vhdx_fd.read(2))[0]
    self.vhdx_fd.seek(20, 1) # Res bytes
    metadata_table = {}
    for _ in range(0, entry_count):
      guid = str(uuid.UUID(bytes_le=self.vhdx_fd.read(16)))
      offset = struct.unpack('<I', self.vhdx_fd.read(4))[0]
      self.vhdx_fd.seek(12, 1) # Metadata length + bit field + res bytes
      metadata_table[guid] = offset
    return metadata_table

  def _ParseFileParam(self):
    """Parses the file parameters metadata entry

    Returns:
      tuple: a tuple containing the block_size and has_parent items
    """
    file_param_offset = self.metadata_table[GUID_FILE_PARAM]
    self.vhdx_fd.seek(self.region_table[GUID_METADATA] + file_param_offset)
    block_size = struct.unpack('<I', self.vhdx_fd.read(4))[0]
    bitfield = self.vhdx_fd.read(1)[0]
    has_parent = False
    if bitfield & (1 << 1):
      has_parent = True
    return (block_size, has_parent)

  def _ParseLogicalSectorSize(self):
    """Parses the logical sector size metadata entry

    Returns:
      int: the parsed logical sector size
    """
    logical_sector_offset = self.metadata_table[GUID_LOGICAL_SECTOR_SIZE]
    self.vhdx_fd.seek(
        self.region_table[GUID_METADATA] + logical_sector_offset)
    logical_sector_size = struct.unpack('<I', self.vhdx_fd.read(4))[0]
    return logical_sector_size

  def _ParseDiskSize(self):
    """Parses the virtual disk size metadata entry

    Returns:
      int: the parsed virtual disk size
    """
    disk_size_offset = self.metadata_table[GUID_DISK_SIZE]
    self.vhdx_fd.seek(self.region_table[GUID_METADATA] + disk_size_offset)
    disk_size = struct.unpack('<Q', self.vhdx_fd.read(8))[0]
    return disk_size

  def _ParseDiskParams(self):
    """Parses the disk params for a VHDX disk

    Returns:
      DiskParams: the parsed disk params
    """
    file_params = self._ParseFileParam()
    block_size = file_params[0]
    has_parent = file_params[1]
    logical_sector_size = self._ParseLogicalSectorSize()
    virtual_disk_size = self._ParseDiskSize()
    sector_count = virtual_disk_size // logical_sector_size

    disk_params = DiskParams(block_size, logical_sector_size,
        virtual_disk_size, has_parent, sector_count)
    logger.debug('Parsed disk params: {disk_params}')
    return disk_params

  def _CalculateBATParams(self):
    """Calculates the BAT params for a VHDX disk

    Returns:
      BATParams: the parsed BAT params
    """
    chunk_ratio = ((2**23*self.disk_params.logical_sector_size) //
        self.disk_params.block_size)
    payload_entries = math.ceil(self.disk_params.virtual_disk_size /
        self.disk_params.block_size)
    sector_bitmap_entries = math.ceil(payload_entries / chunk_ratio)
    if self.disk_params.has_parent:
      total_entries = sector_bitmap_entries * (chunk_ratio+1)
    else:
      total_entries = payload_entries + math.floor(
          (payload_entries-1)/chunk_ratio)

    bat_params = BATParams(chunk_ratio, total_entries, payload_entries,
        sector_bitmap_entries)
    logger.debug('Parsed BAT params: {bat_params}')
    return bat_params

  def _ParseBAT(self):
    """Parses the block allocation table

    Returns:
      BlockAllocationTable: the parsed block allocation table
    """
    self.vhdx_fd.seek(self.region_table[GUID_BAT])
    bat_blocks = self.vhdx_fd.read(
        self.bat_params.total_entries*LEN_BAT_ENTRY)
    return BlockAllocationTable(bat_blocks, self.bat_params)

  def _GetSectorBitmapForBlock(self, block_number):
    """Returns the raw bytes of sector bitmap representing a single data block

    Args:
      block_number (int): the target block number

    Returns:
      list(bool): a list of boolean values representing a sector bitmap

    Raises:
      ValueError: if the sector bitmap block BAT entry state is
        SB_BLOCK_NOT_PRESENT.
    """
    chunk_number = block_number // self.bat_params.chunk_ratio
    sb_entry = self.bat_table.GetSectorBitmapBATEntry(chunk_number)
    if sb_entry.state == 'SB_BLOCK_NOT_PRESENT':
      raise ValueError('Sector bitmap block not present')

    sectors_per_block = (self.disk_params.block_size //
        self.disk_params.logical_sector_size)
    # Number of bitmap block bytes required to represent one data block
    bitmap_bytes_per_block = sectors_per_block // 8
    block_within_chunk = block_number % self.bat_params.chunk_ratio
    # Absolute offset within the sector bitmap of bytes representing the
    # target block's bitmap
    block_bitmap_offset = (block_within_chunk*bitmap_bytes_per_block +
        sb_entry.offset)

    self.vhdx_fd.seek(block_bitmap_offset)
    sector_bitmap_bytes = self.vhdx_fd.read(bitmap_bytes_per_block)
    sector_bitmap = self._ConvertBytesToBitmap(sector_bitmap_bytes)
    return sector_bitmap

  def _ConvertBytesToBitmap(self, sb_bytes):
    """Converts bytes representing a bitmap into a bitmap representation

    Args:
      sb_bytes (bytes): the bytes representing a bitmap

    Returns:
      list: a list of bools representing the bitmap
    """
    bitmap = []
    for sb_byte in sb_bytes:
      for i in range(0, 8):
        if sb_byte & (1<<i):
          bitmap.append(True)
        else:
          bitmap.append(False)
    return bitmap

  def ReadSector(self, sector):
    """Returns a logical sector's contents

    Args:
      sector (int): the sector number

    Returns:
      bytes: the sector contents
    """
    sectors_per_block = (self.disk_params.block_size //
        self.disk_params.logical_sector_size)
    block_number = sector // sectors_per_block
    sector_in_block = sector % sectors_per_block
    bat_entry = self.bat_table.GetPayloadBATEntry(block_number)
    state = bat_entry.state

    if state == 'PAYLOAD_BLOCK_NOT_PRESENT':
      if self.disk_params.has_parent:
        sector = self.parent_disk.ReadSector(sector)
      else:
        sector = self._ReadSectorBytes(bat_entry, sector_in_block)
    elif state == 'PAYLOAD_BLOCK_UNDEFINED':
      sector = self._ReadSectorBytes(bat_entry, sector_in_block)
    elif state == 'PAYLOAD_BLOCK_ZERO':
      sector = b'\x00'*self.disk_params.logical_sector_size
    elif state == 'PAYLOAD_BLOCK_UNMAPPED':
      sector = self._ReadSectorBytes(bat_entry, sector_in_block)
    elif state == 'PAYLOAD_BLOCK_FULLY_PRESENT':
      sector = self._ReadSectorBytes(bat_entry, sector_in_block)
    elif state == 'PAYLOAD_BLOCK_PARTIALLY_PRESENT':
      sector_bitmap = self._GetSectorBitmapForBlock(block_number)
      if sector_bitmap[sector_in_block]:
        sector = self._ReadSectorBytes(bat_entry, sector_in_block)
      else:
        sector = self.parent_disk.ReadSector(sector)

    return sector

  def _ReadSectorBytes(self, bat_entry, sector_in_block):
    """Returns sector contents if an offset is present in the BAT entry
    otherwise return a sector's worth of zero bytes.

    Args:
      bat_entry (PayloadBlockBATEntry): the BAT entry for the block containing
        the target sector
      sector_in_block (int): the target sector within the block

    Returns:
      bytes: either the sector contents or sector_size*b'\x00 if no offset was
        given in the BAT entry
    """
    if bat_entry.offset:
      self.vhdx_fd.seek(bat_entry.offset +
        sector_in_block*self.disk_params.logical_sector_size)
      sector = self.vhdx_fd.read(self.disk_params.logical_sector_size)
    else:
      sector = b'\x00'*self.disk_params.logical_sector_size
    return sector


class MergeVHDXTool:
  """Main class for the MergeVHDXTool tool."""

  def __init__(self):
    """Initializes the MergeVHDXTool class."""
    self._argument_parser = None

  def AddBasicOptions(self, argument_parser):
    """Adds the global options to the argument_parser.

    Args:
      argument_parser(argparse.ArgumentParser): the argument parser to add the
        command to.
    """
    argument_parser.add_argument(
      '-p', '--parent_disk', dest='parent_disk_name', action='store',
      required=True, help='The parent disk to be merged.')
    argument_parser.add_argument(
      '-c', '--child_disk', dest='child_disk_name', action='store',
      required=True, help='The child disk to be merged.')
    argument_parser.add_argument(
      '-o', '--out_image', dest='out_image_name', action='store',
      required=True, help='The output image name.')
    argument_parser.add_argument(
        '-d', '--debug', dest='debug', action='store_true', default=False,
        help='Enable debug messages.')
    argument_parser.add_argument(
        '-y', '--yes', dest='yes', action='store_true', default=False,
        help='Skip confirmations.')

  def ParseArguments(self):
    """Parses the command line arguments.

    Returns:
      argparse.ArgumentParser: the argument parser object.
    """
    self._argument_parser = argparse.ArgumentParser()
    self.AddBasicOptions(self._argument_parser)

    opts = self._argument_parser.parse_args()

    return opts

  def _SetLogging(self, debug):
    """Configures the logging module.

    Args:
      debug(bool): whether to show debug messages.
    """
    handler = logging.StreamHandler()
    logger.setLevel(logging.INFO)

    if debug:
      level = logging.DEBUG
      logger.setLevel(level)
      handler.setLevel(level)

    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] (%(processName)-10s) PID:%(process)d '
        '<%(module)s> %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

  def Main(self):
    """The main method for the MergeVHDXTool class.

    It handles arguments parsing and initiates the disk merge.
    """
    options = self.ParseArguments()
    self._SetLogging(debug=options.debug)

    parent_disk = VHDXDisk(options.parent_disk_name)
    child_disk = VHDXDisk(
        options.child_disk_name, parent_disk=parent_disk)

    with open(options.out_image_name, 'wb') as out_image_fd:
      if not options.yes:
        image_size = child_disk.disk_params.virtual_disk_size//1024**2
        print('This command will create a new disk image of size '
              f'{image_size}MiB.\nPlease confirm (y/n): ', end='')
        confirm = input()
        if confirm.lower() != 'y':
          sys.exit()

      for sector in range(0, child_disk.disk_params.sector_count):
        out_image_fd.write(child_disk.ReadSector(sector))


if __name__ == '__main__':
  MergeVHDXTool().Main()
