import time
import pickle

class Superblock:
    def __init__(self):
        self.block_size = 4096
        self.total_blocks = 1000
        self.inode_table_start = 2  # After inode bitmap (block 1)
        self.total_inodes = 128
        self.inodes_bitmap_start = 1  # Block 1 for inode bitmap
        self.root_dir_inode = 0
        self.free_space_map_start = 4  # Block 4 for free space bitmap

class Inode:
    def __init__(self):
        self.file_size = 0
        self.is_directory = False
        self.creation_time = time.time()
        self.modification_time = time.time()
        self.direct_blocks = [None] * 10  # Space for 10 direct block pointers

class DirectoryEntry:
    def __init__(self, name, inode_num):
        self.name = name
        self.inode_number = inode_num
        self.directory_size = 0  # Placeholder for directory size

class FileEntry:
    def __init__(self, name, inode_num):
        self.name = name
        self.inode_number = inode_num
        self.file_size = 0  # Placeholder for file size

class FileObject:
    def __init__(self, fs_image, inode_number, mode='r'):
        self.fs_image = fs_image
        self.inode_number = inode_number
        self.mode = mode
        self.fs = open(fs_image, 'r+b' if 'w' in mode or 'a' in mode else 'rb')
        from FileOperations import read_inode
        self.inode = read_inode(self.fs, inode_number)
        self.offset = 0

def open_file(fs_image, filename, mode='r', cwd_inode_number=0):
    from FileOperations import read_inode
    sp = Superblock()
    with open(fs_image, 'rb') as fs:
        current_inode = read_inode(fs, cwd_inode_number)
        dir_block = current_inode.direct_blocks[0]
        if dir_block is None:
            print("Directory is empty.")
            return None
        dir_offset = dir_block * sp.block_size
        fs.seek(dir_offset)
        try:
            dir_entries = pickle.load(fs)
        except Exception:
            print("Failed to read directory entries.")
            return None
        for entry in dir_entries:
            if entry.name == filename:
                return FileObject(fs_image, entry.inode_number, mode)
        print(f"File '{filename}' not found.")
        return None