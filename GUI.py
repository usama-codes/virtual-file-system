import tkinter as tk
from tkinter import ttk, messagebox
import sys
import io
from FileOperations import *
from DataStrucures import open_file, close_file
import SystemInitializer

# --- GUI App ---
class VFSApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🗂️ Virtual File System")

        # --- Set fixed window size and center it ---
        window_width = 500
        window_height = 400
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (window_width // 2)
        y = (screen_height // 2) - (window_height // 2)
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.resizable(False, False)

        self.configure(bg="#1e1e1e")

        # --- Improved styling ---
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.style.map('TCombobox', 
        fieldbackground=[('readonly', 'white')],
        background=[('readonly', 'white')],
        foreground=[('readonly', 'black')],
        arrowcolor=[('readonly', 'black')]
        )

        better_font = ("Segoe UI", 10)  # <-- Slightly bigger, sharper font

        self.style.configure("TLabel", background="#1e1e1e", foreground="#d4d4d4", font=better_font)
        self.style.configure("TButton", background="#0e639c", foreground="white", font=better_font)
        self.style.configure("TEntry", fieldbackground="#2d2d30", foreground="white", font=better_font)
        self.style.configure("TCombobox", fieldbackground="#2d2d30", background="#2d2d30", foreground="white", font=better_font)

        self.fs_image = "sample.dat"
        self.cwd_inode = 0

        self.output_capture = io.StringIO()
        sys.stdout = self.output_capture
        self.after(100, self.update_output)

        self.create_widgets()


    def create_widgets(self):
        tk.Label(self, text="Choose Operation:", bg="#1e1e1e", fg="#d4d4d4").pack(pady=10)

        self.operation = ttk.Combobox(self, values=[
            "Create File", "Read File", "Delete File", "Make Directory",
            "Change Directory", "Move File", "Open File", "Close File",
            "Show Memory Map", "Write to File", "Read from File",
            "Move Within File", "Truncate File"
        ], state="readonly")
        self.operation.pack(pady=5)
        self.operation.bind("<<ComboboxSelected>>", self.show_fields)

        self.current_dir_label = ttk.Label(self, text="Current Directory: /", font=("Segoe UI", 8))
        self.current_dir_label.pack(pady=5)

        self.fields_frame = tk.Frame(self, bg="#1e1e1e")
        self.fields_frame.pack(pady=10)

        self.execute_btn = tk.Button(self, text="Execute", command=self.run_command, bg="#0e639c", fg="white")
        self.execute_btn.pack(pady=10)

        self.output = tk.Text(self, height=6, bg="#252526", fg="#d4d4d4", wrap="word")
        self.output.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def update_output(self):
        new_output = self.output_capture.getvalue()
        if new_output:
            self.output.insert(tk.END, new_output)
            self.output_capture.truncate(0)
            self.output_capture.seek(0)
            self.output.see(tk.END)
        self.after(100, self.update_output)

    def show_fields(self, event):
        for widget in self.fields_frame.winfo_children():
            widget.destroy()

        op = self.operation.get()
        self.inputs = {}

        def add_field(name, is_dropdown=False, options=None):
            label = ttk.Label(self.fields_frame, text=name + ":")
            label.pack()
            if is_dropdown:
                entry = ttk.Combobox(self.fields_frame, values=options or [], state="readonly")
            else:
                entry = ttk.Entry(self.fields_frame)
            entry.pack(fill=tk.X)
            self.inputs[name] = entry

        fields_map = {
            "Create File": ["Filename", "Content"],
            "Read File": ["Filename"],
            "Delete File": ["Filename"],
            "Make Directory": ["Directory Name"],
            "Move File": ["Source Filename", "Target Directory"],
            "Open File": ["Filename"],
            "Close File": ["Filename"],
            "Write to File": ["Filename", "Content"],
            "Read from File": ["Filename", "Start (optional)", "Size (optional)"],
            "Move Within File": ["Filename", "Start", "Size", "Target"],
            "Truncate File": ["Filename", "Max Size"]
        }

        if op == "Change Directory":
            dirs = self.get_available_directories()
            add_field("Directory Name", is_dropdown=True, options=dirs)
        else:
            for field in fields_map.get(op, []):
                add_field(field)

    def get_available_directories(self):
        dirs = [".. (Go Up)"]
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
        except:
            pass
        return dirs

    def run_command(self):
        op = self.operation.get()
        get = lambda name: self.inputs[name].get()
        self.output.delete(1.0, tk.END)

        try:
            if op == "Create File":
                createFile(self.fs_image, get("Filename"), get("Content"), self.cwd_inode)

            elif op == "Read File":
                readFile(self.fs_image, get("Filename"), self.cwd_inode)

            elif op == "Delete File":
                deleteFile(self.fs_image, get("Filename"), self.cwd_inode)

            elif op == "Make Directory":
                mkdir(self.fs_image, get("Directory Name"), self.cwd_inode)

            elif op == "Change Directory":
                dir_name = get("Directory Name")
                if dir_name == ".. (Go Up)":
                    self.cwd_inode = 0
                    self.current_dir_label.config(text="Current Directory: /")
                else:
                    new_inode = chdir(self.fs_image, dir_name, self.cwd_inode)
                    if new_inode != self.cwd_inode:
                        self.cwd_inode = new_inode
                        self.current_dir_label.config(text=f"Current Directory: /{dir_name}")


            elif op == "Move File":
                move(self.fs_image, get("Source Filename"), get("Target Directory"), self.cwd_inode)

            elif op == "Open File":
                open_file(self.fs_image, get("Filename"), "w", self.cwd_inode)

            elif op == "Close File":
                close_file(get("Filename"))

            elif op == "Show Memory Map":
                show_memory_map(self.fs_image)

            elif op == "Write to File":
                f = open_file(self.fs_image, get("Filename"), "w", self.cwd_inode)
                if f:
                    f.Write_to_file(get("Content"))
                    close_file(get("Filename"))

            elif op == "Read from File":
                f = open_file(self.fs_image, get("Filename"), "r", self.cwd_inode)
                if f:
                    start = get("Start (optional)")
                    size = get("Size (optional)")
                    result = f.Read_from_file(int(start) if start else None, int(size) if size else None)
                    print(result)
                    close_file(get("Filename"))

            elif op == "Move Within File":
                f = open_file(self.fs_image, get("Filename"), "w", self.cwd_inode)
                if f:
                    f.Move_within_file(int(get("Start")), int(get("Size")), int(get("Target")))
                    close_file(get("Filename"))

            elif op == "Truncate File":
                f = open_file(self.fs_image, get("Filename"), "w", self.cwd_inode)
                if f:
                    f.Truncate_file(int(get("Max Size")))
                    close_file(get("Filename"))

        except Exception as e:
            print(f"⚠️ Error: {e}")

        for widget in self.fields_frame.winfo_children():
            widget.destroy()    # Also clear input fields

if __name__ == "__main__":
    app = VFSApp()
    app.mainloop()
