import customtkinter as ctk
import sys, io, pickle
from FileOperations import *
from DataStrucures import open_file, close_file
import SystemInitializer

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class VFSApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("🗂️ Virtual File System")
        self.geometry("800x500")
        self.resizable(False, False)

        self.fs_image = "sample.dat"
        self.cwd_inode = 0
        self.output_capture = io.StringIO()
        sys.stdout = self.output_capture
        self.after(100, self.update_output)

        self.create_widgets()

    def create_widgets(self):
        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=200)
        self.sidebar.pack(side="left", fill="y", padx=10, pady=10)

        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(side="right", expand=True, fill="both", padx=10, pady=10)

        self.buttons = {}
        self.operations = [
            "Create File", "Read File", "Delete File", "Make Directory",
            "Change Directory", "Move File", "Open File", "Close File",
            "Show Memory Map", "Write to File", "Read from File",
            "Move Within File", "Truncate File"
        ]

        for op in self.operations:
            btn = ctk.CTkButton(self.sidebar, text=op, corner_radius=20, fg_color="#d3d3d3", text_color="black",
                                hover_color="#c0c0c0", command=lambda o=op: self.select_operation(o))
            btn.pack(pady=4, fill="x")
            self.buttons[op] = btn

        self.current_dir_label = ctk.CTkLabel(self.main_frame, text="Current Directory: /", anchor="w")
        self.current_dir_label.pack(pady=5, fill="x")

        self.fields_frame = ctk.CTkFrame(self.main_frame)
        self.fields_frame.pack(fill="x", pady=10)

        self.execute_btn = ctk.CTkButton(self.main_frame, text="Execute", command=self.run_command)
        self.execute_btn.pack(pady=5)

        self.output = ctk.CTkTextbox(self.main_frame, height=100)
        self.output.pack(fill="both", expand=True, padx=5, pady=10)

        self.current_operation = None
        self.inputs = {}

    def update_output(self):
        new_output = self.output_capture.getvalue()
        if new_output:
            self.output.insert("end", new_output)
            self.output_capture.truncate(0)
            self.output_capture.seek(0)
            self.output.see("end")
        self.after(100, self.update_output)

    def select_operation(self, operation):
        self.current_operation = operation

        # Highlight selection
        for op, btn in self.buttons.items():
            btn.configure(fg_color="white" if op != operation else "#1e90ff", text_color="black")

        for widget in self.fields_frame.winfo_children():
            widget.destroy()
        self.inputs = {}

        def add_field(name):
            label = ctk.CTkLabel(self.fields_frame, text=name + ":")
            label.pack()
            entry = ctk.CTkEntry(self.fields_frame)
            entry.pack(fill="x", pady=2)
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

        if operation == "Change Directory":
            dirs = self.get_available_directories()
            label = ctk.CTkLabel(self.fields_frame, text="Directory Name:")
            label.pack()
            entry = ctk.CTkComboBox(self.fields_frame, values=dirs)
            entry.pack(fill="x", pady=2)
            self.inputs["Directory Name"] = entry
        else:
            for field in fields_map.get(operation, []):
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
        op = self.current_operation
        get = lambda name: self.inputs[name].get()
        self.output.delete("1.0", "end")

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
                    self.current_dir_label.configure(text="Current Directory: /")
                else:
                    new_inode = chdir(self.fs_image, dir_name, self.cwd_inode)
                    if new_inode != self.cwd_inode:
                        self.cwd_inode = new_inode
                        self.current_dir_label.configure(text=f"Current Directory: /{dir_name}")

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

if __name__ == "__main__":
    app = VFSApp()
    app.mainloop()
