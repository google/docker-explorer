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
"""Classes to represent a VHDX virtual disk"""

import uuid
import struct
import math
import logging
import sys


class BlockAllocationTableEntry:
  """Represents a VHDX block allocation table entry.

  Attributes:
    state (int): the state of BAT entry
    offset (int): the offset of the block the BAT entry points to
  """

  def __init__(self, bat_bytes):
    """Initialises a BlockAllocationTableEntry

    Args:
      bat_bytes (bytes): a bytes object representing the BAT entry
    """
    state_bitmask = 0b00000111
    offset_lead_byte_bitmask = 0b11110000
    self.state = bat_bytes[0] & state_bitmask
    offset_lead_byte = bat_bytes[2] & offset_lead_byte_bitmask
    offset_bytes = b'\x00'*2 + bytes([offset_lead_byte]) + bat_bytes[3:]
    self.offset = struct.unpack("<Q", offset_bytes)[0]


class BlockAllocationTable:
  """Represents a VHDX block allocation table.

  Attributes:
    data_blocks (list(BlockAllocationTableEntry): a list of BAT data blocks
    sector_bitmap_blocks (list(BlockAllocationTableEntry)): a list of sector
      bitmap blocks
  """
  def __init__(self, data_blocks, sector_bitmap_blocks):
    """Initialises a BlockAllocationTable.

    Args:
      data_blocks (list): a list of BAT data blocks
      sector_bitmap_blocks: a list of sector bitmap blocks
    """
    self.data_blocks = data_blocks
    self.sector_bitmap_blocks = sector_bitmap_blocks
    self.logger = logging.getLogger()

  def GetDBEntryForBlock(self, block_number):
    """Returns a data block entry for for a given block number

    Args:
      block_number (int): the block number to retrieve an entry for
    """
    return self.data_blocks[block_number]

  def GetSBForChunk(self, chunk_number):
    """Returns a sector bitmap block for for a given chunk number

    Args:
      chunk_number (int): the chunk number to retrieve an entry for
    """
    return self.sector_bitmap_blocks[chunk_number]


class VHDXDisk:
  """Represents a VHDX virtual disk.

  Attributes:
    vhdx_name (str): the on-disk name of the VHDX file
    vhdx_fd (file): the open VHDX file
    parent_disk (VHDXDisk): The parent disk if this is a differencing disk
    region_table (list((UUID, int))): A list of VHDX regions represented as
      UUID/offset tuples
    bat_offset (int): the offset of the BAT table
    metadata_table_offset (int): the offset of the metadata table
    metadata_table (list((UUID, int))): A list of metadata entries represented
      UUID/offset tuples
    block_size (int): the parsed VHDX block size
    has_parent (bool): the parsed parent indicator
    logical_sector_size (int): the parsed logical sector size
    virtual_disk_size (int): the parsed virtual disk size
    chunk_ratio (int): the calculated chunk size
    data_block_count (int): the calculated data block count
    sector_bitmap_block_count (int): the calculated bitmap block count
    total_bat_entries (int): the calculated total BAT entries
    bat_table (BlockAllocationTable): the parsed block allocation table
  """

  REGION_HEADER_OFFSET = 192*1024
  GUID_BAT = '2dc27766-f623-4200-9d64-115e9bfd4a08'
  GUID_METADATA = '8b7ca206-4790-4b9a-b8fe-575f050f886e'
  GUID_FILE_PARAM = 'caa16737-fa36-4d43-b3b6-33f0aa44e76b'
  GUID_DISK_SIZE = '2fa54224-cd1b-4876-b211-5dbed83bf4b8'
  GUID_DISK_ID = 'beca12ab-b2e6-4523-93ef-c309e000c746'
  GUID_LOGICAL_SECTOR_SIZE = '8141bf1d-a96f-4709-ba47-f233a8faab5f'
  GUID_PHYSICAL_SECTOR_SIZE = 'cda348c7-445d-4471-9cc9-e9885251c556'
  GUID_PARENT_LOCATOR = 'a8d35f2d-b30b-454d-abf7-d3d84834ab0c'
  PAYLOAD_BLOCK_NOT_PRESENT = 0
  PAYLOAD_BLOCK_UNDEFINED = 1
  PAYLOAD_BLOCK_ZERO = 2
  PAYLOAD_BLOCK_UNMAPPED = 3
  PAYLOAD_BLOCK_FULLY_PRESENT = 6
  PAYLOAD_BLOCK_PARTIALLY_PRESENT = 7
  SB_BLOCK_NOT_PRESENT = 0
  SB_BLOCK_PRESENT = 6

  def __init__(self, vhdx_name, parent_disk=None):
    """Initialises a VHDXDisk

    Args:
      vhdx_name (str): the name of the target VHDX file
      parent_disk (VHDXDisk) Optional: the parent disk if this is a child disk
    """
    self.vhdx_name = vhdx_name
    self.vhdx_fd = open(vhdx_name, 'rb')
    self.parent_disk = parent_disk
    self.region_table = self._ParseRegionTable()
    self.bat_offset = self.region_table[self.GUID_BAT]
    self.metadata_table_offset = self.region_table[self.GUID_METADATA]
    self.metadata_table = self._ParseMetadataTable()
    file_params = self._ParseFileParam()
    self.block_size = file_params[0]
    self.has_parent = file_params[1]
    self.logical_sector_size = self._ParseLogicalSectorSize()
    self.virtual_disk_size = self._ParseDiskSize()
    self.chunk_ratio = (2**23 * self.logical_sector_size) // self.block_size
    self.data_block_count = math.ceil(
        self.virtual_disk_size // self.block_size)
    self.sector_bitmap_block_count = math.ceil(
        self.data_block_count // self.chunk_ratio)
    if self.has_parent:
      self.total_bat_entries = self.sector_bitmap_block_count * (
          self.chunk_ratio + 1)
    else:
      self.total_bat_entries = self.data_block_count + math.floor(
          (self.data_block_count-1)/self.chunk_ratio)
    self.bat_table = self._ParseBat()
    self.logger = logging.getLogger()

  def _ParseRegionTable(self):
    """Parses a region table from a VHDX disk

    Returns:
      list((UUID, int)): A list of VHDX regions represented as UUID/offset
        tuples
    """
    self.vhdx_fd.seek(self.REGION_HEADER_OFFSET)
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
      list((UUID, int)): A list of metadata items represented as UUID/offset
        tuples
    """
    self.vhdx_fd.seek(self.metadata_table_offset)
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
      (int, int): a tuple containing the block_size and has_parent items
    """
    file_param_offset = self.metadata_table[self.GUID_FILE_PARAM]
    self.vhdx_fd.seek(self.metadata_table_offset + file_param_offset)
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
    logical_sector_offset = self.metadata_table[self.GUID_LOGICAL_SECTOR_SIZE]
    self.vhdx_fd.seek(self.metadata_table_offset + logical_sector_offset)
    logical_sector_size = struct.unpack('<I', self.vhdx_fd.read(4))[0]
    return logical_sector_size

  def _ParseDiskSize(self):
    """Parses the virtual disk size metadata entry

    Returns:
      int: the parsed virtual disk size
    """
    disk_size_offset = self.metadata_table[self.GUID_DISK_SIZE]
    self.vhdx_fd.seek(self.metadata_table_offset + disk_size_offset)
    disk_size = struct.unpack('<Q', self.vhdx_fd.read(8))[0]
    return disk_size

  def _ParseBat(self):
    """Parses the block allocation table

    Returns:
      BlockAllocationTable: the parsed block allocation table
    """
    data_blocks = []
    sector_bitmap_blocks = []
    last_block_idx = self.total_bat_entries
    self.vhdx_fd.seek(self.bat_offset)
    for idx in range(0, self.total_bat_entries+1):
      parsed_entry = BlockAllocationTableEntry(self.vhdx_fd.read(8))
      if idx == last_block_idx:
        if self.has_parent:
          sector_bitmap_blocks.append(parsed_entry)
        else:
          data_blocks.append(parsed_entry)
      elif idx != 0 and idx % self.chunk_ratio == 0:
        sector_bitmap_blocks.append(parsed_entry)
      else:
        data_blocks.append(parsed_entry)

    bat_table = BlockAllocationTable(data_blocks, sector_bitmap_blocks)
    return bat_table

  def _GetSectorBitmapForBlock(self, block_number):
    """Returns the raw bytes of sector bitmap representing a single data block

    Args:
      block_number (int): the target block number

    Returns:
      bytes: the raw bytes object representing a sector bitmap for the target
        block
    """
    chunk_number = block_number // self.chunk_ratio
    sb_entry = self.bat_table.GetSBForChunk(chunk_number)
    if sb_entry.state == self.SB_BLOCK_NOT_PRESENT:
      raise ValueError
    sb_entry_offset = sb_entry.offset
    sectors_per_block = self.block_size // self.logical_sector_size
    # Number of bitmap block bytes required to represent one data block
    bitmap_bytes_per_block = sectors_per_block // 8
    block_within_chunk = block_number % self.chunk_ratio
    # Absolute offset within the sector bitmap of bytes representing the
    # target block
    block_bitmap_offset = (
      block_within_chunk*bitmap_bytes_per_block + sb_entry_offset)
    self.vhdx_fd.seek(block_bitmap_offset)
    sector_bitmap_bytes = self.vhdx_fd.read(bitmap_bytes_per_block)
    return sector_bitmap_bytes

  def _ConvertBytesToBitmap(self, sb_bytes):
    """Converts bytes representing a bitmap into a bitmap representation

    Args:
      sb_bytes (bytes): the bytes representing a bitmap

    Returns:
      list(bool): a list of bools representing the bitmap
    """
    bitmap = []
    for sb_byte in sb_bytes:
      for i in range(7, -1, -1):
        if sb_byte & (1<<i):
          bitmap.append(True)
        else:
          bitmap.append(False)
    return bitmap

  def _GetPartialDataBlock(self, block_number):
    """Parses a partially present block in a child disk

    Represents state PAYLOAD_BLOCK_PARTIALLY_PRESENT where a block is only
    partially present within the child disk with some sectors present in the
    parent.

    Args:
      block_number (int): the target block number

    Returns:
      bytes: representing the given block
    """
    sector_bitmap_bytes = self._GetSectorBitmapForBlock(block_number)
    sector_bitmap = self._ConvertBytesToBitmap(sector_bitmap_bytes)
    sectors_per_block = self.block_size // self.logical_sector_size
    block_offset = self.bat_table.GetDBEntryForBlock(block_number).offset
    parsed_block = bytearray()
    self.vhdx_fd.seek(block_offset)
    for sector in range(0, sectors_per_block):
      if sector_bitmap[sector]:
        parsed_block += bytearray(self.vhdx_fd.read(self.logical_sector_size))
      else:
        parsed_block += bytearray(
          self.parent_disk.GetLogicalSector(block_number, sector))
        self.vhdx_fd.seek(self.logical_sector_size, 1)
    return parsed_block

  def _GetLogicalSectorIfPresent(self, bat_entry, sector_in_block):
    """Returns sector contents if an offset is present'

    For certain block states the specification states that read behaviour can
    either return the contents previously in the block or zeros.

    Args:
      bat_entry (BlockAllocationTableEntry): the BAT entry for the block
        containing the target sector
      sector_in_block (int): the target sector within the block

    Returns:
      bytes: either the sector contents or sector_size*b'\x00 if no offset was
        given in the BAT entry
    """
    if bat_entry.offset:
      self.vhdx_fd.seek(
        bat_entry.offset + sector_in_block*self.logical_sector_size)
      sector = self.vhdx_fd.read(self.logical_sector_size)
    else:
      sector = b'\x00'*self.logical_sector_size
    return sector

  def GetLogicalSector(self, block_number, sector_in_block):
    """Returns a logical sector's contents

    Args:
      block_number (int): the block containing the sector
      sector_in_block (int): the sector number within the target block

    Returns:
      bytes: the sector contents
    """
    bat_entry = self.bat_table.GetDBEntryForBlock(block_number)
    state = bat_entry.state

    if state == self.PAYLOAD_BLOCK_NOT_PRESENT:
      if self.has_parent:
        sector = self.parent_disk.GetLogicalSector(
          block_number, sector_in_block)
      else:
        sector = self._GetLogicalSectorIfPresent(bat_entry, sector_in_block)
    elif state == self.PAYLOAD_BLOCK_UNDEFINED:
      sector = self._GetLogicalSectorIfPresent(bat_entry, sector_in_block)
    elif state == self.PAYLOAD_BLOCK_ZERO:
      sector = b'\x00'*self.logical_sector_size
    elif state == self.PAYLOAD_BLOCK_UNMAPPED:
      sector = self._GetLogicalSectorIfPresent(bat_entry, sector_in_block)
    elif state == self.PAYLOAD_BLOCK_FULLY_PRESENT:
      self.vhdx_fd.seek(
        bat_entry.offset + sector_in_block*self.logical_sector_size)
      sector = self.vhdx_fd.read(self.logical_sector_size)
    elif state == self.PAYLOAD_BLOCK_PARTIALLY_PRESENT:
      sector = self.parent_disk.GetLogicalSector(
        block_number, sector_in_block)

    return sector

  def _GetDataBlockIfPresent(self, bat_entry):
    """Returns block contents if an offset is present'

    For certain block states the specification states that read behaviour can
    either return the contents previously in the block or zeros.

    Args:
      bat_entry (BlockAllocationTableEntry): the BAT entry for the block
        containing the target sector
      sector_in_block (int): the target sector within the block

    Returns:
      bytes: either the block contents or block_size*b'\x00 if no offset was
        given in the BAT entry
    """
    if bat_entry.offset:
      self.vhdx_fd.seek(bat_entry.offset)
      parsed_block = self.vhdx_fd.read(self.block_size)
    else:
      parsed_block = b'\x00'*self.block_size
    return parsed_block

  def GetDataBlock(self, block_number):
    """Returns a data block's contents

    Args:
      block_number (int): the target block number

    Returns:
      bytes: the block contents
    """
    if block_number >= len(self.bat_table.data_blocks):
      raise ValueError('Requested block out of range')
    bat_entry = self.bat_table.GetDBEntryForBlock(block_number)
    state = bat_entry.state

    if state == self.PAYLOAD_BLOCK_NOT_PRESENT:
      if self.has_parent:
        parsed_block = self.parent_disk.GetDataBlock(block_number)
      else:
        parsed_block = self._GetDataBlockIfPresent(bat_entry)
    elif state == self.PAYLOAD_BLOCK_UNDEFINED:
      parsed_block = self._GetDataBlockIfPresent(bat_entry)
    elif state == self.PAYLOAD_BLOCK_ZERO:
      parsed_block = b'\x00'*self.block_size
    elif state == self.PAYLOAD_BLOCK_UNMAPPED:
      parsed_block = self._GetDataBlockIfPresent(bat_entry)
    elif state == self.PAYLOAD_BLOCK_FULLY_PRESENT:
      self.vhdx_fd.seek(bat_entry.offset)
      parsed_block = self.vhdx_fd.read(self.block_size)
    elif state == self.PAYLOAD_BLOCK_PARTIALLY_PRESENT:
      parsed_block = self._GetPartialDataBlock(block_number)

    return parsed_block


if __name__ == '__main__':
  parent = VHDXDisk(sys.argv[1])
  child = VHDXDisk(sys.argv[2], parent)
  out = open('converted.raw', 'wb')
  for block in range(0, 20480):
    out.write(child.GetDataBlock(block))
    child.GetDataBlock(block)
