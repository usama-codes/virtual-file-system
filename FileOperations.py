from DataStrucures import Superblock, Inode, DirectoryEntry, get_thread_open_file_table, open_file, FileObject, close_file
import pickle
import time

sp = Superblock()
INODE_SIZE = 256  # Adjust if needed
fs_image = "sample.dat"  # Default filesystem image

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

def createFile(fs_image, filename, content, cwd_inode_number=0):
    with open(fs_image, 'r+b') as fs:
        block_bitmap = read_block_bitmap(fs)
        parent_inode = read_inode(fs, cwd_inode_number)
        parent_dir_block = parent_inode.direct_blocks[0]
        if parent_dir_block is None:
            print("Directory is empty.")
            return
        dir_offset = parent_dir_block * sp.block_size
        fs.seek(dir_offset)
        try:
            dir_entries = pickle.load(fs)
        except Exception:
            dir_entries = []

        # Check if file already exists
        for entry in dir_entries:
            if entry.name == filename:
                print(f"File '{filename}' already exists.")
                return

        # Allocate blocks for file content
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

        # Write content to blocks
        for index, block_num in enumerate(free_blocks):
            data_offset = block_num * block_size
            fs.seek(data_offset)
            start = index * block_size
            end = start + block_size
            fs.write(content_bytes[start:end])

        write_block_bitmap(fs, block_bitmap)

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

        # Create inode for the new file
        inode = Inode()
        inode.file_size = len(content_bytes)
        inode.creation_time = time.time()
        inode.modification_time = time.time()
        for i, block_num in enumerate(free_blocks):
            inode.direct_blocks[i] = block_num
        write_inode(fs, free_inode_index, inode)
        write_inode_bitmap(fs, inode_bitmap)

        # ✅ Correct: just update existing dir_entries, don't reload again
        dir_entries.append(DirectoryEntry(filename, free_inode_index))
        fs.seek(dir_offset)
        fs.write(pickle.dumps(dir_entries))
        print(f"File '{filename}' created in {fs_image} (directory inode {cwd_inode_number}) with content: {content}")


def readFile(fs_image, filename, cwd_inode_number=0):
    with open(fs_image, 'rb') as fs:
        current_inode = read_inode(fs, cwd_inode_number)
        dir_block = current_inode.direct_blocks[0]
        if dir_block is None:
            print("Directory is empty.")
            return
        dir_offset = dir_block * sp.block_size
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

def deleteFile(fs_image, filename, cwd_inode_number=0):
    with open(fs_image, 'r+b') as fs:
        parent_inode = read_inode(fs, cwd_inode_number)
        parent_dir_block = parent_inode.direct_blocks[0]
        if parent_dir_block is None:
            print("Directory is empty.")
            return
        dir_offset = parent_dir_block * sp.block_size
        fs.seek(dir_offset)
        try:
            dir_entries = pickle.load(fs)
        except Exception:
            print("No directory entries found.")
            return
        
        entry_to_remove = None
        for entry in dir_entries:
            if entry.name == filename:
                inode = read_inode(fs, entry.inode_number)
                if inode.is_directory:
                    print(f"⚠️ '{filename}' is a directory. Cannot delete a directory using deleteFile().")
                    return
                else:
                    entry_to_remove = entry
                    break
        
        if not entry_to_remove:
            print(f"File '{filename}' not found.")
            return

        # Remove file entry
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

        print(f"✅ File '{filename}' deleted from {fs_image} (directory inode {cwd_inode_number}).")

def mkdir(fs_image, dirname, cwd_inode_number=0):
    with open(fs_image, 'r+b') as fs:
        # First check if a directory with this name already exists
        cwd_inode = read_inode(fs, cwd_inode_number)
        cwd_dir_block = cwd_inode.direct_blocks[0]
        cwd_dir_offset = cwd_dir_block * sp.block_size
        fs.seek(cwd_dir_offset)
        try:
            dir_entries = pickle.load(fs)
            # Check if directory with same name exists
            for entry in dir_entries:
                if entry.name == dirname:
                    print(f"Directory '{dirname}' already exists.")
                    return
        except Exception:
            dir_entries = []

        # Find a free inode for the new directory
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

        # Find a free block for the new directory
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

        # Create a new inode for the directory
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

        # Update the parent directory (current directory, not always root)
        cwd_inode = read_inode(fs, cwd_inode_number)
        cwd_dir_block = cwd_inode.direct_blocks[0]
        cwd_dir_offset = cwd_dir_block * sp.block_size
        fs.seek(cwd_dir_offset)
        try:
            dir_entries = pickle.load(fs)
        except Exception:
            dir_entries = []
        
        # Add the new directory to the parent directory's entries
        dir_entries.append(DirectoryEntry(dirname, free_inode_index))

        # Re-seek and overwrite the directory entries
        fs.seek(cwd_dir_offset)
        pickle.dump(dir_entries, fs)
        fs.flush()  # Force write to disk

        # Zero-fill the rest of the block
        end_pos = fs.tell()
        bytes_used = end_pos - cwd_dir_offset
        padding = sp.block_size - (bytes_used % sp.block_size)

        if padding < sp.block_size:  # Don't pad if we're exactly at block boundary
            fs.write(b'\x00' * padding)
        fs.flush()  # Make sure padding is written

        # Write updated block bitmap
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
# Special handling if target_dir_name == ".." meaning move to root
        if target_dir_name == "..":
            target_inode = read_inode(fs, 0)  # Root inode
            target_dir_block = target_inode.direct_blocks[0]
        else:
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
            target_dir_block = target_inode.direct_blocks[0]

        if target_dir_block is None:
            print(f"Target directory '{target_dir_name}' has no data block.")
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


def get_available_directories(self):
    dirs = []
    try:
        with open(self.fs_image, 'rb') as fs:
            current_inode = read_inode(fs, self.cwd_inode)
            dir_block = current_inode.direct_blocks[0]
            if dir_block is not None:
                fs.seek(dir_block * sp.block_size)
                entries = pickle.load(fs)
                for entry in entries:
                    entry_inode = read_inode(fs, entry.inode_number)
                    if entry_inode.is_directory:
                        dirs.append(entry.name)
        if self.cwd_inode != 0:
            dirs.insert(0, ".. (Go Up)")  # Only show ".." if not already at root
    except:
        pass
    return dirs


def show_memory_map(fs_image, output=None):
    output_lines = []

    def write(line):
        if output:
            output.write(line + "\n")
        else:
            output_lines.append(line)

    write("\nFilesystem Memory Map\n")

    def dfs(fs, inode_num, indent=0):
        inode = read_inode(fs, inode_num)
        prefix = "    " * indent

        if inode.is_directory:
            if inode_num == 0:
                write(f"{prefix}📁 /")
            else:
                write(f"{prefix}📁 {current_name[0]}")

            dir_block = inode.direct_blocks[0]
            if dir_block is not None:
                fs.seek(dir_block * sp.block_size)
                try:
                    entries = pickle.load(fs)
                    entries = sorted(entries, key=lambda e: e.name)
                    for entry in entries:
                        entry_inode = read_inode(fs, entry.inode_number)
                        current_name[0] = entry.name
                        dfs(fs, entry.inode_number, indent + 1)
                except Exception as e:
                    write(f"{prefix}⚠️ Failed to read entries: {e}")
        else:
            write(f"{prefix}📄 {current_name[0]}")

    with open(fs_image, 'rb') as fs:
        sp = Superblock()
        current_name = ["/"]
        dfs(fs, 0)

    if output:
        return None  # Already written to stream
    return "\n".join(output_lines)


def execute_command(command, outfile=None):
    parts = command.strip().split()

    if not parts:
        return "Empty command."

    cmd = parts[0].lower()
    oft = get_thread_open_file_table()

    # I. Create(fName)
    if cmd == "create" and len(parts) == 2:
        filename = parts[1]
        createFile(fs_image, filename, "", 0)
        return f"File {filename} created."

    # II. Delete(fName)
    elif cmd == "delete" and len(parts) == 2:
        filename = parts[1]
        deleteFile(fs_image, filename, 0)
        return f"File {filename} deleted."

    # III. Mkdir(dirName)
    elif cmd == "mkdir" and len(parts) == 2:
        dirname = parts[1]
        mkdir(fs_image, dirname, 0)
        return f"Directory {dirname} created."

    # IV. chDir(dirName)
    elif cmd == "chdir" and len(parts) == 2:
        dirname = parts[1]
        chdir(fs_image, dirname,0)
        return f"Changed directory to {dirname}."

    # V. Move(source_fName, target_fName)
    elif cmd == "move" and len(parts) == 3:
        src = parts[1]
        dest = parts[2]
        move(fs_image, src, dest, 0)
        return f"Moved {src} to {dest}."

    # VI. Open(fName, mode)
    elif cmd == "open" and len(parts) == 3:
        filename = parts[1]
        mode = parts[2]
        open_file(fs_image, filename, mode, 0)
        return f"File {filename} opened in {mode} mode."

    # VII. Close(fName)
    elif cmd == "close" and len(parts) == 2:
        filename = parts[1]
        close_file(filename)
        return f"File {filename} closed."

    # VIII. Write to file: write_to_file(fName, "text") or write_to_file(fName, position, "text")
    elif cmd == "write_to_file":
        if len(parts) >= 3:
            filename = parts[1]
            file_obj = oft.get(filename)
            if not file_obj:
                return f"Error: {filename} is not open"

            if parts[2].isdigit():
                # write_to_file(filename, position, "text")
                write_at = int(parts[2])
                data = command.split('"', 1)[1].rsplit('"', 1)[0]
                file_obj.write_to_file(write_at, data)
                return f"Wrote to {filename} at position {write_at}: {data}"
            else:
                # write_to_file(filename, "text")
                data = command.split('"', 1)[1].rsplit('"', 1)[0]
                file_obj.Write_to_file(data)
                return f"Wrote to {filename}: {data}"

    # IX. Read from file: read_from_file(fName) or read_from_file(fName, start, size)
    elif cmd == "read_from_file":
        if len(parts) == 2:
            filename = parts[1]
            file_obj = oft.get(filename)
            if not file_obj:
                return f"Error: {filename} is not open"
            data = file_obj.Read_from_file()
            return f"Data from {filename}: {data}"
        elif len(parts) == 4:
            filename = parts[1]
            start = int(parts[2])
            size = int(parts[3])
            file_obj = oft.get(filename)
            if not file_obj:
                return f"Error: {filename} is not open"
            data = file_obj.Read_from_file(start, size)
            return f"Data from {filename} (from {start} for {size}): {data}"

    # X. Move within file: move_within_file(fName, start, size, target)
    elif cmd == "move_within_file" and len(parts) == 5:
        filename = parts[1]
        start = int(parts[2])
        size = int(parts[3])
        target = int(parts[4])
        file_obj = oft.get(filename)
        if not file_obj:
            return f"Error: {filename} is not open"
        file_obj.Move_within_file(start, size, target)
        return f"Moved {size} bytes in {filename} from {start} to {target}."

    # XI. Truncate file: truncate_file(fName, maxSize)
    elif cmd == "truncate_file" and len(parts) == 3:
        filename = parts[1]
        max_size = int(parts[2])
        file_obj = oft.get(filename)
        if not file_obj:
            return f"Error: {filename} is not open"
        file_obj.Truncate_file(max_size)
        return f"Truncated {filename} to max size {max_size}."

    # XII. Show memory map
    elif cmd == "show_memory_map":
            return show_memory_map(fs_image)  # This function already handles printing.

    # Invalid command
    return "Invalid or malformed command."

if __name__ == "__main__":
    fs_image = "sample.dat"
    createFile(fs_image, "test.txt", "Hello, World!")
    open_file(fs_image, "test.txt", "r")
    readFile(fs_image, "test.txt")
