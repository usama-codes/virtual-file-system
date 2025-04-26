import time
import pickle

# Global table to keep track of open files
open_file_table = {}

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
    def Write_to_file(self, text):
        """Append text at the end of the file."""
        self.write_to_file(self.inode.file_size, text)

    def write_to_file(self, index, text):
        from FileOperations import write_inode
        sp = Superblock()
        block_size = sp.block_size
        content_bytes = text.encode('utf-8')

        # Read current file content
        existing = bytearray()
        bytes_left = self.inode.file_size
        for block in self.inode.direct_blocks:
            if block and bytes_left > 0:
                self.fs.seek(block * block_size)
                read_len = min(bytes_left, block_size)
                existing += self.fs.read(read_len)
                bytes_left -= read_len

        # Pad if needed and inject new content
        if index > len(existing):
            existing.extend(b' ' * (index - len(existing)))
        new_data = existing[:index] + content_bytes
        new_data += existing[index + len(content_bytes):] if index + len(content_bytes) < len(existing) else b''

        # Calculate required blocks
        total_size = len(new_data)
        blocks_needed = (total_size + block_size - 1) // block_size

        # Load and update block bitmap
        bitmap_offset = sp.free_space_map_start * block_size
        self.fs.seek(bitmap_offset)
        bitmap = bytearray(self.fs.read(block_size))

        used_blocks = []
        for i in range(blocks_needed):
            if i < len(self.inode.direct_blocks) and self.inode.direct_blocks[i]:
                used_blocks.append(self.inode.direct_blocks[i])
            else:
                for b, bit in enumerate(bitmap):
                    if bit == 0:
                        block_num = b + sp.free_space_map_start + 1
                        bitmap[b] = 1
                        used_blocks.append(block_num)
                        if i < len(self.inode.direct_blocks):
                            self.inode.direct_blocks[i] = block_num
                        break

        # Write new data
        for i, block in enumerate(used_blocks):
            self.fs.seek(block * block_size)
            self.fs.write(new_data[i * block_size: (i + 1) * block_size])

        # Save inode and bitmap
        self.fs.seek(bitmap_offset)
        self.fs.write(bitmap)
        self.inode.file_size = total_size
        self.inode.modification_time = time.time()
        write_inode(self.fs, self.inode_number, self.inode)

        print(f"Wrote {len(content_bytes)} bytes at index {index}.")

    def Read_from_file(self, start=None, size=None):
        """If no arguments: returns full content. If start and size are given: returns partial content."""
        sp = Superblock()
        block_size = sp.block_size

        file_size = self.inode.file_size
        if start is None or size is None:
            start = 0
            size = file_size

        if start >= file_size:
            print("Start offset beyond file size.")
            return ""

        size = min(size, file_size - start)  # clamp size to file bounds
        result = bytearray()
        remaining = size

        # Calculate where to start
        current_block_idx = start // block_size
        block_offset = start % block_size

        while remaining > 0 and current_block_idx < len(self.inode.direct_blocks):
            block_num = self.inode.direct_blocks[current_block_idx]
            if block_num is None:
                break  # sparse region or unallocated

            self.fs.seek(block_num * block_size + block_offset)
            read_len = min(remaining, block_size - block_offset)
            result += self.fs.read(read_len)

            remaining -= read_len
            current_block_idx += 1
            block_offset = 0  # reset after first block

        return result.decode('utf-8')
    def Move_within_file(self, start, size, target):
        """Moves a segment of data from (start to start+size) to index 'target'."""
        sp = Superblock()
        block_size = sp.block_size

        # Step 1: Read entire content
        content = self.Read_from_file()

        if start < 0 or size < 0 or target < 0:
            print("Invalid negative value.")
            return
        if start + size > len(content):
            print("Range to move exceeds file size.")
            return

        # Step 2: Extract and reinsert
        moving_segment = content[start:start + size]
        remaining = content[:start] + content[start + size:]

        # Clamp target to file bounds
        target = min(target, len(remaining))

        new_content = remaining[:target] + moving_segment + remaining[target:]

        # Step 3: Overwrite file with new content
        self.write_to_file(0, new_content)  # write from beginning
        print(f"Moved {size} bytes from index {start} to {target}.")

    def Truncate_file(self, maxSize):
        sp = Superblock()
        block_size = sp.block_size
        current_size = self.inode.file_size

        # Step 1: Read current content
        content = self.Read_from_file()

        # Step 2: Truncate or pad
        if maxSize < current_size:
            new_content = content[:maxSize]
        elif maxSize > current_size:
            new_content = content + (' ' * (maxSize - current_size))
        else:
            print("File already at specified size.")
            return

        # Step 3: Write new content back to file
        self.write_to_file(0, new_content)

        # Step 4: Deallocate unused blocks if shrinking
        blocks_needed = (len(new_content) + block_size - 1) // block_size
        all_blocks = self.inode.direct_blocks

        if blocks_needed < len(all_blocks):
            block_bitmap_offset = sp.free_space_map_start * block_size
            self.fs.seek(block_bitmap_offset)
            bitmap = bytearray(self.fs.read(block_size))

            for i in range(blocks_needed, len(all_blocks)):
                block = all_blocks[i]
                if block is not None:
                    block_index = block - sp.free_space_map_start - 1
                    if 0 <= block_index < len(bitmap):
                        bitmap[block_index] = 0
                    self.inode.direct_blocks[i] = None

            # Save bitmap
            self.fs.seek(block_bitmap_offset)
            self.fs.write(bitmap)

        # Step 5: Update inode
        self.inode.file_size = maxSize
        self.inode.modification_time = time.time()
        from FileOperations import write_inode
        write_inode(self.fs, self.inode_number, self.inode)

        print(f"Truncated file to {maxSize} bytes.")


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
                print("file is opened")
                file_obj = FileObject(fs_image, entry.inode_number, mode)
                open_file_table[filename] = file_obj
                return file_obj               
        print(f"File '{filename}' not found.")
        return None
    

# Function to close a file
def close_file(filename):
    global open_file_table

    if filename in open_file_table:
        file_obj = open_file_table[filename]
        file_obj.fs.close()  # Close the actual file stream
        del open_file_table[filename]  # Remove from open table
        print(f"File '{filename}' closed.")
    else:
        print(f"File '{filename}' is not currently open.")
