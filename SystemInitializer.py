from DataStrucures import Superblock, Inode
import pickle

def initialize_filesystem(filename, size_mb=10):
    total_bytes = size_mb * 1024 * 1024
    block_size = 4096
    total_blocks = total_bytes // block_size

    sb = Superblock()
    sb.total_blocks = total_blocks

    with open(filename, 'wb') as f:
        write_superblock(f, sb)
        # Write inode bitmap (root inode used)
        inode_bitmap = bytearray([0] * sb.total_inodes)
        inode_bitmap[0] = 1
        write_inode_bitmap(f, inode_bitmap, sb.inodes_bitmap_start * block_size)
        # Write fixed-size inode table
        write_inode_table(f, sb, block_size)
        # Write free space bitmap (all free)
        write_bitmap(f, bytearray([0] * block_size), sb.free_space_map_start * block_size)
        # Initialize root directory block (empty list)
        root_dir_block = 5  # First data block after bitmaps

        block_bitmap = bytearray([0] * sb.block_size)  # sb.block_size = 4096
        block_index = root_dir_block - sb.free_space_map_start - 1  # 5 - 4 - 1 = 0
        block_bitmap[block_index] = 1  # Mark block 5 as used
        write_bitmap(f, block_bitmap, sb.free_space_map_start * sb.block_size)

        root_inode_offset = sb.inode_table_start * block_size
        f.seek(root_inode_offset)
        root_inode = Inode()
        root_inode.is_directory = True
        root_inode.direct_blocks[0] = root_dir_block
        f.write(pickle.dumps(root_inode))
        # Write empty directory entries to root directory block
        f.seek(root_dir_block * block_size)
        pickle.dump([], f)

def serialize(obj):
    return pickle.dumps(obj)

def write_superblock(f, superblock):
    f.seek(0)
    f.write(serialize(superblock))

def write_inode_bitmap(f, bitmap, offset):
    f.seek(offset)
    f.write(bitmap)

def write_inode_table(f, sb, block_size):
    f.seek(sb.inode_table_start * block_size)
    for i in range(sb.total_inodes):
        inode = Inode()
        if i == 0:
            inode.is_directory = True
            inode.direct_blocks[0] = 5  # Root directory block
        f.write(serialize(inode))

def write_bitmap(f, bitmap, offset):
    f.seek(offset)
    f.write(bitmap)

if __name__ == "__main__":
    filename = 'sample.dat'
    size_mb = 10
    initialize_filesystem(filename, size_mb)