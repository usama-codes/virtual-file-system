from DataStrucures import Superblock, Inode, DirectoryEntry
import pickle
import time

sp = Superblock()
INODE_SIZE = 256  # Adjust if needed

def read_inode_bitmap(fs):
    inode_bitmap_offset = sp.inodes_bitmap_start * sp.block_size
    fs.seek(inode_bitmap_offset)
    return bytearray(fs.read(sp.total_inodes))

def write_inode_bitmap(fs, bitmap):
    inode_bitmap_offset = sp.inodes_bitmap_start * sp.block_size
    fs.seek(inode_bitmap_offset)
    fs.write(bitmap)

def read_inode(fs, index):
    inode_offset = sp.inode_table_start * sp.block_size + index * INODE_SIZE
    fs.seek(inode_offset)
    return pickle.load(fs)

def write_inode(fs, index, inode):
    inode_offset = sp.inode_table_start * sp.block_size + index * INODE_SIZE
    fs.seek(inode_offset)
    fs.write(pickle.dumps(inode))

def read_block_bitmap(fs):
    bitmap_offset = sp.free_space_map_start * sp.block_size
    fs.seek(bitmap_offset)
    return bytearray(fs.read(sp.block_size))

def write_block_bitmap(fs, bitmap):
    bitmap_offset = sp.free_space_map_start * sp.block_size
    fs.seek(bitmap_offset)
    fs.write(bitmap)

def createFile(fs_image, filename, content):
    with open(fs_image, 'r+b') as fs:
        block_bitmap = read_block_bitmap(fs)
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
            dir_entries = []
        for entry in dir_entries:
            if entry.name == filename:
                print(f"File '{filename}' already exists.")
                return
        content_bytes = content.encode('utf-8')
        block_size = sp.block_size
        num_blocks_needed = (len(content_bytes) + block_size - 1) // block_size
        if num_blocks_needed > 10:
            print("File too large for this simple file system (max 10 blocks).")
            return
        free_blocks = []
        for i, bit in enumerate(block_bitmap):
            if bit == 0:
                free_blocks.append(i + sp.free_space_map_start + 1)
                block_bitmap[i] = 1
                if len(free_blocks) == num_blocks_needed:
                    break
        if len(free_blocks) < num_blocks_needed:
            print("Not enough free data blocks available.")
            return
        for index, block_num in enumerate(free_blocks):
            data_offset = block_num * block_size
            fs.seek(data_offset)
            start = index * block_size
            end = start + block_size
            fs.write(content_bytes[start:end])
        write_block_bitmap(fs, block_bitmap)
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
        inode = Inode()
        inode.file_size = len(content_bytes)
        inode.creation_time = time.time()
        inode.modification_time = time.time()
        for i, block_num in enumerate(free_blocks):
            inode.direct_blocks[i] = block_num
        write_inode(fs, free_inode_index, inode)
        write_inode_bitmap(fs, inode_bitmap)
        fs.seek(dir_offset)
        try:
            dir_entries = pickle.load(fs)
        except Exception:
            dir_entries = []
        dir_entries.append(DirectoryEntry(filename, free_inode_index))
        fs.seek(dir_offset)
        fs.write(pickle.dumps(dir_entries))
        print(f"File '{filename}' created in {fs_image} with content: {content}")

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
        entry_to_remove = None
        for entry in dir_entries:
            if entry.name == filename:
                entry_to_remove = entry
                break
        if not entry_to_remove:
            print(f"File '{filename}' not found.")
            return
        dir_entries.remove(entry_to_remove)
        inode_bitmap = read_inode_bitmap(fs)
        inode_bitmap[entry_to_remove.inode_number] = 0
        write_inode_bitmap(fs, inode_bitmap)
        inode = read_inode(fs, entry_to_remove.inode_number)
        block_bitmap = read_block_bitmap(fs)
        for block in inode.direct_blocks:
            if block is not None:
                block_index = block - sp.free_space_map_start - 1
                if 0 <= block_index < len(block_bitmap):
                    block_bitmap[block_index] = 0
        write_block_bitmap(fs, block_bitmap)
        write_inode(fs, entry_to_remove.inode_number, Inode())
        fs.seek(dir_offset)
        fs.write(pickle.dumps(dir_entries))
        print(f"File '{filename}' deleted from {fs_image}.")

def mkdir(fs_image, dirname):
    with open(fs_image, 'r+b') as fs:
        # First check if a directory with this name already exists
        root_inode = read_inode(fs, 0)
        root_dir_block = root_inode.direct_blocks[0]
        root_dir_offset = root_dir_block * sp.block_size
        fs.seek(root_dir_offset)
        try:
            dir_entries = pickle.load(fs)
            # Check if directory with same name exists
            for entry in dir_entries:
                if entry.name == dirname:
                    print(f"Directory '{dirname}' already exists.")
                    return
        except Exception:
            dir_entries = []

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
        block_bitmap = read_block_bitmap(fs)
        free_block = None
        for i, bit in enumerate(block_bitmap):
            if bit == 0:
                free_block = i + sp.free_space_map_start + 1
                block_bitmap[i] = 1
                break
        if free_block is None:
            print("No free data blocks available.")
            return
        inode = Inode()
        inode.is_directory = True
        inode.file_size = 0
        inode.creation_time = time.time()
        inode.modification_time = time.time()
        inode.direct_blocks[0] = free_block
        write_inode(fs, free_inode_index, inode)
        write_inode_bitmap(fs, inode_bitmap)
        # Initialize the new directory block with an empty list
        dir_offset = free_block * sp.block_size
        fs.seek(dir_offset)
        pickle.dump([], fs)
        # Update the parent directory (root)
        root_inode = read_inode(fs, 0)
        root_dir_block = root_inode.direct_blocks[0]
        root_dir_offset = root_dir_block * sp.block_size
        fs.seek(root_dir_offset)
        try:
            dir_entries = pickle.load(fs)
        except Exception:
            dir_entries = []
        dir_entries.append(DirectoryEntry(dirname, free_inode_index))
        # Re-seek and overwrite the directory entries
        fs.seek(root_dir_offset)
        pickle.dump(dir_entries, fs)
        fs.flush()  # Force write to disk

        # Zero-fill the rest of the block
        end_pos = fs.tell()
        bytes_used = end_pos - root_dir_offset
        padding = sp.block_size - (bytes_used % sp.block_size)

        if padding < sp.block_size:  # Don't pad if we're exactly at block boundary
            fs.write(b'\x00' * padding)
        fs.flush()  # Make sure padding is written

        write_block_bitmap(fs, block_bitmap)
        print(f"Directory '{dirname}' created in {fs_image}.")

def chdir(fs_image, dirname, cwd_inode_number=0):
    with open(fs_image, 'rb') as fs:
        current_inode = read_inode(fs, cwd_inode_number)
        if not current_inode.is_directory:
            print("Current inode is not a directory.")
            return cwd_inode_number
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
    with open(fs_image, 'r+b') as fs:
        current_inode = read_inode(fs, cwd_inode_number)
        if not current_inode.is_directory:
            print("Current inode is not a directory.")
            return
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
        source_entry = None
        for entry in dir_entries:
            if entry.name == source_name:
                source_entry = entry
                break
        if not source_entry:
            print(f"Source '{source_name}' not found in current directory.")
            return
        target_dir_entry = None
        for entry in dir_entries:
            if entry.name == target_dir_name:
                target_dir_entry = entry
                break
        if not target_dir_entry:
            print(f"Target directory '{target_dir_name}' not found in current directory.")
            return
        target_inode = read_inode(fs, target_dir_entry.inode_number)
        if not target_inode.is_directory:
            print(f"Target '{target_dir_name}' is not a directory.")
            return
        dir_entries.remove(source_entry)
        fs.seek(dir_offset)
        fs.write(pickle.dumps(dir_entries))
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

def print_root_directory(fs_image):
    with open(fs_image, 'rb') as fs:
        root_inode = read_inode(fs, 0)
        root_dir_block = root_inode.direct_blocks[0]
        if root_dir_block is None:
            print("Root directory is empty.")
            return
        dir_offset = root_dir_block * sp.block_size
        fs.seek(dir_offset)
        try:
            dir_entries = pickle.load(fs)
            print("Root directory entries:")
            for entry in dir_entries:
                print(f"  Name: {entry.name}, Inode: {entry.inode_number}")
        except Exception as e:
            print("Failed to read directory entries:", e)

def print_directory_tree(fs_image, inode_number=0, indent=0):
    with open(fs_image, 'rb') as fs:
        inode = read_inode(fs, inode_number)
        if not inode.is_directory:
            print(" " * indent + f"(file) inode {inode_number}")
            return
        dir_block = inode.direct_blocks[0]
        if dir_block is None:
            print(" " * indent + f"(empty dir) inode {inode_number}")
            return
        dir_offset = dir_block * sp.block_size
        fs.seek(dir_offset)
        try:
            dir_entries = pickle.load(fs)
        except Exception:
            print(" " * indent + "(unreadable directory)")
            return

        for entry in dir_entries:
            entry_inode = read_inode(fs, entry.inode_number)
            if entry_inode.is_directory:
                print(" " * indent + f"[DIR] {entry.name} (inode {entry.inode_number})")
                print_directory_tree(fs_image, entry.inode_number, indent + 4)
            else:
                print(" " * indent + f"[FILE] {entry.name} (inode {entry.inode_number})")

if __name__ == "__main__":
    fs_image = "sample.dat"
    # mkdir(fs_image, "test_dir")
    # mkdir(fs_image, "test_dir2")
    # mkdir(fs_image, "test_dir3")

    # createFile(fs_image, "test_dir/test_file.txt", "Hello, World!")
    # readFile(fs_image, "test_dir/test_file.txt")

    # createFile(fs_image, "test_dir2/test_file2.txt", "Another file.")
    # readFile(fs_image, "test_dir2/test_file2.txt")

    # createFile(fs_image, "test_dir3/test_file3.txt", "Yet another file.")
    # readFile(fs_image, "test_dir3/test_file3.txt")

    # print_root_directory(fs_image)
    print_directory_tree(fs_image, 0)