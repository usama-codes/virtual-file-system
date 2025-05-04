import shutil
import threading
import sys

from FileOperations import execute_command  # Make sure you have this in FileOperations.py

# Global lock for thread synchronization (used in FileOperations)
filesystem_lock = threading.Lock()

# Worker function for each thread
def thread_worker(thread_id):
    input_filename = f"input_thread{thread_id}.txt"
    output_filename = f"output_thread{thread_id}.txt"

    try:
        with open(input_filename, "r") as infile, open(output_filename, "w", encoding="utf-8") as outfile:
            for line in infile:
                command = line.strip()
                if not command:
                    continue

                with filesystem_lock:
                    try:
                        result = execute_command(command, outfile)
                    except Exception as e:
                        result = f"Error: {str(e)}"

                outfile.write(f"{result}\n")
    except FileNotFoundError:
        print(f"[Thread {thread_id}] Input file '{input_filename}' not found.")

def create_input_file_copies(master_file, num_threads):
    # Loop through the number of threads and create the copies
    for i in range(0, num_threads):
        # Define the new file name
        new_filename = f"input_thread{i}.txt"
        # Copy the master file to the new file
        shutil.copy(master_file, new_filename)
        print(f"Created {new_filename} from {master_file}")


def main():
    if len(sys.argv) != 2:
        print("Usage: python main.py <number_of_threads>")
        sys.exit(1)

    try:
        num_threads = int(sys.argv[1])
    except ValueError:
        print("Error: Number of threads must be an integer.")
        sys.exit(1)

    master_input_file = "input.txt"  # This is your source file
    # Create copies of the master file
    create_input_file_copies(master_input_file, num_threads)

    threads = []

    for thread_id in range(num_threads):
        t = threading.Thread(target=thread_worker, args=(thread_id,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    print("All threads completed.")

if __name__ == "__main__":
    main()
