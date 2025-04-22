from DataStrucures import Superblock, Inode
import pickle

def initialize_filesystem(filename, size_mb=10):
    total_bytes = size_mb * 1024 * 1024
    block_size = 4096
    total_blocks = total_bytes // block_size

    sb = Superblock()
    sb.total_blocks = total_blocks
    sb.is_directory = True

    with open(filename, 'wb') as f:
        write_superblock(f, sb)
        # Write inode bitmap
        inode_bitmap = bytearray([0] * sb.total_inodes)
        inode_bitmap[0] = 1  # Mark root inode as used
        write_inode_bitmap(f, inode_bitmap, sb.inodes_bitmap_start * block_size)
        # Write fixed-size inode table
        write_inode_table(f, sb, block_size)
        write_bitmap(f, b'\x00' * (block_size - 1), sb.free_space_map_start * block_size)
        
    print(f"Filesystem initialized with {total_blocks} blocks of size {block_size} bytes.")

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
            inode.is_directory = True  # Root inode is a directory
        f.write(serialize(inode))

def write_bitmap(f, bitmap, offset):
    f.seek(offset)
    f.write(bitmap)

if __name__ == "__main__":
    filename = 'sample.dat'
    size_mb = 10  # Size of the filesystem in MB
    initialize_filesystem(filename, size_mb)