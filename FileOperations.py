from DataStrucures import Superblock, Inode, DirectoryEntry
import pickle
import time

sp = Superblock()

# Function to read the inode bitmap to check for free inode entry
def read_inode_bitmap(fs):
    inode_bitmap_offset = sp.inodes_bitmap_start * sp.block_size
    fs.seek(inode_bitmap_offset)
    return bytearray(fs.read(sp.total_inodes))

# Function to write the inode bitmap after updating it
def write_inode_bitmap(fs, bitmap):
    inode_bitmap_offset = sp.inodes_bitmap_start * sp.block_size
    fs.seek(inode_bitmap_offset)
    fs.write(bitmap)

# Function to read the inode with given index
def read_inode(fs, index):
    inode_offset = sp.inode_table_start * sp.block_size + index * 256  # Assume 256 bytes per inode
    fs.seek(inode_offset)
    return pickle.load(fs)

# Function to write to inode with given index
def write_inode(fs, index, inode):
    inode_offset = sp.inode_table_start * sp.block_size + index * 256
    fs.seek(inode_offset)
    fs.write(pickle.dumps(inode))

def createFile(fs_image, filename, content):
    with open(fs_image, 'r+b') as fs:
        # Load block bitmap
        bitmap_offset = sp.free_space_map_start * sp.block_size
        fs.seek(bitmap_offset)
        bitmap = bytearray(fs.read(sp.block_size))  # Read the bitmap

        # Check if the file already exists in the root directory
        root_inode = read_inode(fs, 0)
        root_dir_block = root_inode.direct_blocks[0]
        if root_dir_block is None:
            print("Root directory is empty.")
            return

        # Read the root directory entries
        dir_offset = root_dir_block * sp.block_size
        fs.seek(dir_offset)
        try:
            dir_entries = pickle.load(fs)
        except Exception:
            print("Failed to read directory entries.")
            return

        for entry in dir_entries:
            if entry.name == filename:
                print(f"File '{filename}' already exists.")
                return

        # Split content into blocks
        content_bytes = content.encode('utf-8')
        block_size = sp.block_size
        num_blocks_needed = (len(content_bytes) + block_size - 1) // block_size

        if num_blocks_needed > 10:
            print("File too large for this simple file system (max 10 blocks).")
            return

        # Find free data blocks
        free_blocks = []
        for i, bit in enumerate(bitmap):
            if bit == 0:
                free_blocks.append(i + sp.free_space_map_start + 1)
                bitmap[i] = 1
                if len(free_blocks) == num_blocks_needed:
                    break
        if len(free_blocks) < num_blocks_needed:
            print("Not enough free data blocks available.")
            return

        # Write content to the free data blocks
        for index, block_num in enumerate(free_blocks):
            data_offset = block_num * block_size
            fs.seek(data_offset)
            start = index * block_size
            end = start + block_size
            fs.write(content_bytes[start:end])

        # Update block bitmap
        fs.seek(bitmap_offset)
        fs.write(bitmap)

        # Find a free inode using inode bitmap
        inode_bitmap = read_inode_bitmap(fs)
        free_inode_index = None
        for index, bit in enumerate(inode_bitmap):
            if bit == 0:
                free_inode_index = index
                inode_bitmap[index] = 1
                break
        if free_inode_index is None:
            print("No free inodes available.")
            return

        # Update inode metadata and write to fixed location
        inode = Inode()
        inode.file_size = len(content_bytes)
        inode.creation_time = time.time()
        inode.modification_time = time.time()
        for i, block_num in enumerate(free_blocks):
            inode.direct_blocks[i] = block_num
        write_inode(fs, free_inode_index, inode)
        write_inode_bitmap(fs, inode_bitmap)

        # Update root directory
        root_inode = read_inode(fs, 0)
        root_dir_block = root_inode.direct_blocks[0]
        dir_offset = root_dir_block * block_size
        fs.seek(dir_offset)
        try:
            dir_entries = pickle.load(fs)
        except Exception:
            dir_entries = []
        dir_entries.append(DirectoryEntry(filename, free_inode_index))
        fs.seek(dir_offset)
        fs.write(pickle.dumps(dir_entries))

        print(f"File '{filename}' created in {fs_image} with content: {content}")

# Function to read a file
def readFile(fs_image, filename):
    with open(fs_image, 'rb') as fs:
        root_inode = read_inode(fs, 0)
        root_dir_block = root_inode.direct_blocks[0]
        dir_offset = root_dir_block * sp.block_size
        fs.seek(dir_offset)
        try:
            dir_entries = pickle.load(fs)
        except Exception:
            print("Failed to read directory entries.")
            return
        
        file_inode_num = None
        for entry in dir_entries:
            if entry.name == filename:
                file_inode_num = entry.inode_number
                break
        if file_inode_num is None:
            print(f"File '{filename}' not found.")
            return
        
        inode = read_inode(fs, file_inode_num)
        content_bytes = b''
        bytes_left = inode.file_size
        for block_num in inode.direct_blocks:
            if block_num is not None and bytes_left > 0:
                data_offset = block_num * sp.block_size
                fs.seek(data_offset)
                to_read = min(bytes_left, sp.block_size)
                content_bytes += fs.read(to_read)
                bytes_left -= to_read
        print(content_bytes.decode('utf-8'))

def deleteFile(fs_image, filename):
    with open(fs_image, 'r+b') as fs:
        # Load root inode and directory entries
        root_inode = read_inode(fs, 0)
        root_dir_block = root_inode.direct_blocks[0]
        if root_dir_block is None:
            print("Root directory is empty.")
            return
        dir_offset = root_dir_block * sp.block_size
        fs.seek(dir_offset)
        try:
            dir_entries = pickle.load(fs)
        except Exception:
            print("No directory entries found.")
            return

        # Find and remove the directory entry for the file
        entry_to_remove = None
        for entry in dir_entries:
            if entry.name == filename:
                entry_to_remove = entry
                break
        if not entry_to_remove:
            print(f"File '{filename}' not found.")
            return
        dir_entries.remove(entry_to_remove)

        # Mark inode as free in inode bitmap
        inode_bitmap = read_inode_bitmap(fs)
        inode_bitmap[entry_to_remove.inode_number] = 0
        write_inode_bitmap(fs, inode_bitmap)

        # Mark data blocks as free in data block bitmap
        inode = read_inode(fs, entry_to_remove.inode_number)
        bitmap_offset = sp.free_space_map_start * sp.block_size
        fs.seek(bitmap_offset)
        block_bitmap = bytearray(fs.read(sp.block_size))
        for block in inode.direct_blocks:
            if block is not None:
                block_index = block - sp.free_space_map_start - 1
                if 0 <= block_index < len(block_bitmap):
                    block_bitmap[block_index] = 0
        fs.seek(bitmap_offset)
        fs.write(block_bitmap)

        # Zero out the inode
        write_inode(fs, entry_to_remove.inode_number, Inode())

        # Write updated directory entries back
        fs.seek(dir_offset)
        fs.write(pickle.dumps(dir_entries))

        print(f"File '{filename}' deleted from {fs_image}.")

def mkdir(fs_image, dirname):
    with open(fs_image, 'r+b') as fs:
        # Find a free inode
        inode_bitmap = read_inode_bitmap(fs)
        free_inode_index = None
        for index, bit in enumerate(inode_bitmap):
            if bit == 0:
                free_inode_index = index
                inode_bitmap[index] = 1
                break
        if free_inode_index is None:
            print("No free inodes available.")
            return

        # Find a free data block
        bitmap_offset = sp.free_space_map_start * sp.block_size
        fs.seek(bitmap_offset)
        block_bitmap = bytearray(fs.read(sp.block_size))
        free_block = None
        for i, bit in enumerate(block_bitmap):
            if bit == 0:
                free_block = i + sp.free_space_map_start + 1
                block_bitmap[i] = 1
                break
        if free_block is None:
            print("No free data blocks available.")
            return

        # Create and write the new directory inode
        inode = Inode()
        inode.is_directory = True
        inode.file_size = 0
        inode.creation_time = time.time()
        inode.modification_time = time.time()
        inode.direct_blocks[0] = free_block
        write_inode(fs, free_inode_index, inode)
        write_inode_bitmap(fs, inode_bitmap)

        # Initialize the new directory's data block (empty list)
        dir_offset = free_block * sp.block_size
        fs.seek(dir_offset)
        pickle.dump([], fs)

        # Add entry to parent directory (root)
        root_inode = read_inode(fs, 0)
        root_dir_block = root_inode.direct_blocks[0]
        dir_offset = root_dir_block * sp.block_size
        fs.seek(dir_offset)
        try:
            dir_entries = pickle.load(fs)
        except Exception:
            dir_entries = []
        dir_entries.append(DirectoryEntry(dirname, free_inode_index))
        fs.seek(dir_offset)
        pickle.dump(dir_entries, fs)

        # Update block bitmap
        fs.seek(bitmap_offset)
        fs.write(block_bitmap)

        print(f"Directory '{dirname}' created in {fs_image}.")

def chdir(fs_image, dirname, cwd_inode_number=0):
    """
    Change the current working directory to 'dirname' inside the directory represented by cwd_inode_number.
    Returns the new cwd_inode_number if successful, else returns the old one.
    """
    with open(fs_image, 'rb') as fs:
        # Read the current directory's inode
        current_inode = read_inode(fs, cwd_inode_number)
        if not current_inode.is_directory:
            print("Current inode is not a directory.")
            return cwd_inode_number

        # Read directory entries from its data block
        dir_block = current_inode.direct_blocks[0]
        if dir_block is None:
            print("Directory is empty.")
            return cwd_inode_number
        dir_offset = dir_block * sp.block_size
        fs.seek(dir_offset)
        try:
            dir_entries = pickle.load(fs)
        except Exception:
            print("Failed to read directory entries.")
            return cwd_inode_number

        # Search for the destination directory
        for entry in dir_entries:
            if entry.name == dirname:
                dest_inode = read_inode(fs, entry.inode_number)
                if dest_inode.is_directory:
                    print(f"Changed directory to '{dirname}'.")
                    return entry.inode_number
                else:
                    print(f"'{dirname}' is not a directory.")
                    return cwd_inode_number

        print(f"Directory '{dirname}' not found.")
        return cwd_inode_number

def move(fs_image, source_name, target_dir_name, cwd_inode_number=0):
    """
    Move a file from the current directory to another directory (target_dir_name).
    Only updates directory entries; does not move file data or inode.
    """
    with open(fs_image, 'r+b') as fs:
        # Read current directory's inode and entries
        current_inode = read_inode(fs, cwd_inode_number)
        if not current_inode.is_directory:
            print("Current inode is not a directory.")
            return

        # Load current directory entries
        dir_block = current_inode.direct_blocks[0]
        if dir_block is None:
            print("Current directory is empty.")
            return
        dir_offset = dir_block * sp.block_size
        fs.seek(dir_offset)
        try:
            dir_entries = pickle.load(fs)
        except Exception:
            print("Failed to read directory entries.")
            return

        # Find the source entry
        source_entry = None
        for entry in dir_entries:
            if entry.name == source_name:
                source_entry = entry
                break
        if not source_entry:
            print(f"Source '{source_name}' not found in current directory.")
            return

        # Find the target directory entry
        target_dir_entry = None
        for entry in dir_entries:
            if entry.name == target_dir_name:
                target_dir_entry = entry
                break
        if not target_dir_entry:
            print(f"Target directory '{target_dir_name}' not found in current directory.")
            return

        # Check that the target is a directory
        target_inode = read_inode(fs, target_dir_entry.inode_number)
        if not target_inode.is_directory:
            print(f"Target '{target_dir_name}' is not a directory.")
            return

        # Remove the source entry from the current directory
        dir_entries.remove(source_entry)
        fs.seek(dir_offset)
        fs.write(pickle.dumps(dir_entries))

        # Add the source entry to the target directory's entries
        target_dir_block = target_inode.direct_blocks[0]
        if target_dir_block is None:
            print(f"Target directory '{target_dir_name}' has no data block.")
            return
        target_dir_offset = target_dir_block * sp.block_size
        fs.seek(target_dir_offset)
        try:
            target_dir_entries = pickle.load(fs)
        except Exception:
            target_dir_entries = []
        target_dir_entries.append(source_entry)
        fs.seek(target_dir_offset)
        fs.write(pickle.dumps(target_dir_entries))

        print(f"Moved '{source_name}' to directory '{target_dir_name}'.")

if __name__ == "__main__":
    fs_image = "sample.dat"
    createFile(fs_image, "testfile.txt", "Hello, World!")

    file_to_delete = "testfile.txt"
    deleteFile(fs_image, file_to_delete)

    mkdir(fs_image, "test2dir")
    mkdir(fs_image, "testdir")
    chdir(fs_image, "testdir")
    move(fs_image, "testfile.txt", "testdir")