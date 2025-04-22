import time
import pickle

class Superblock:
    def __init__(self):
        self.block_size = 4096  # 4KB blocks
        self.total_blocks = 1000  # Total number of blocks in the filesystem
        self.inode_table_start = 1  # Block number where inode table starts
        self.total_inodes = 128  # Total number of inodes
        self.inodes_bitmap_start = 4  # Block number where inode bitmap starts
        self.root_dir_inode = 0  # First inode is root directory
        self.free_space_map_start = 5  # Block number where free space bitmap starts
        
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

# Function to open a file in the filesystem
def open_file(fs_image, filename, mode='r', cwd_inode_number=0):
    sp = Superblock()
    
    from FileOperations import read_inode

    with open(fs_image, 'rb') as fs:
        # Find the file in the current directory
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