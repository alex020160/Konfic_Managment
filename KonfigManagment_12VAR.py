# -*- foding: utf-8 -*-
import tkinter as tk
from tkinter import scrolledtext
import sys, io, os, shlex, getpass, socket, argparse
import time
import stat

username = getpass.getuser()
hostname = socket.gethostname()

parser = argparse.ArgumentParser(description="GUI emulator with VFS and startup script")
parser.add_argument("--vfs", type=str, default=os.path.expanduser("~"),
                    help="Path to the 'root' of the virtual file system (VFS) (home directory).")
parser.add_argument("--script", type=str, default=None,
                    help="Path to the emulator command startup script (optional).")
args = parser.parse_args()
vfs_root = os.path.abspath(args.vfs)
current_directory = "";



def make_path_vfs(path: str) -> str:
    """
    Пользовательский путь -> абсолютный путь внутри vfs_root.
    Поддерживает '/' и '\', '~', точки, '..'. Не даёт вылезти из vfs_root.
    """
    p = (path or ".").strip().replace("\\", "/")  # нормализуем бэкслеши

    # '~' трактуем как корень VFS
    if p.startswith("~"):
        p = "/" + p[1:]

    # абсолютный ("/...") или относительный путь?
    if p == "/":
        rel = ""                          # корень VFS
    elif p.startswith("/"):
        rel = p.lstrip("/")
    else:
        base = current_directory          # '' или 'sub/dir'
        rel = os.path.normpath(os.path.join(base, p))

    abs_path = os.path.normpath(os.path.join(vfs_root, rel))

    # защита от выхода за VFS
    vr = os.path.normpath(vfs_root)
    try:
        if os.path.commonpath([abs_path, vr]) != vr:
            return vr
    except Exception:
        return vr

    return abs_path


def path_rel_to_vfs(abs_path: str) -> str:
    """Абсолютный путь внутри VFS -> отображаемый путь для пользователя (с ведущим '/')."""
    vr = os.path.normpath(vfs_root)
    ap = os.path.normpath(abs_path)
    if ap == vr:
        return "/"
    rel = os.path.relpath(ap, vr).replace("\\", "/")
    return "/" + ("" if rel in (".", "") else rel)



if not os.path.isdir(vfs_root):
    print(f"[Error] --vfs must point to an existing directory: {vfs_root}", file=sys.stderr);
    sys.exit(2);




def output_to_console(text: str="", end: str=""):
    console.insert("end", text+ end);
    console.see("end");


def output_text(text: str = ""):
    output_to_console(text + "\n");



def make_prompt() -> str:
    shown = "/" if not current_directory else "/" + current_directory.replace("\\", "/")
    return f"[{username}@{hostname} {shown}]# "


ListOfCommands = {"exit", "ls", "cd", "pwd"}

root = tk.Tk()
root.title(f"Emulator - [{username}@{hostname}]")



console = scrolledtext.ScrolledText(
    root, width=100, height=28,
    font=("Consolas", 12),
    fg="black", bg="white",
    insertbackground="black", wrap="none"
)
console.pack(padx=10, pady=10)

prompt = make_prompt()
console.insert("end", prompt)

guard_index = console.index(f"end-1c - {len(prompt)}c")  
console.mark_set("insert", f"{guard_index}+{len(prompt)}c")
console.focus_set()


output_text("start parametrs at debugging");
output_text(f"--vfs: {vfs_root}");
output_text(f"--script: {args.script if args.script else '(no script)'}")


def get_current_line_command(line: str):
    try:
        parts = shlex.split(line, posix=False)  # важно для Windows: '\' не экранирует
    except ValueError as e:
        raise ValueError(f"Error of parsing: {e}")
    if not parts:
        return "", ""
    return parts[0], " ".join(parts[1:]) if len(parts) > 1 else ""




def parse_ls_args(arg: str):
    """
    Поддержка флагов: -l (long), -r (reverse).
    Возвращает (flags:set[str], paths:list[str], err:str|None)
    """
    flags = set()
    paths = []
    tokens = shlex.split(arg) if arg else []
    for t in tokens:
        if t.startswith("-") and t != "-":
            for ch in t[1:]:
                if ch in ("l", "r"):
                    flags.add(ch)
                else:
                    return None, None, f"ls: invalid option -- {ch}"
        else:
            paths.append(t)
    if not paths:
        paths = ["."]
    return flags, paths, None

def mark_dirname(base_abs: str, name: str) -> str:
    return name + ("/" if os.path.isdir(os.path.join(base_abs, name)) else "")

def format_long_entry(base_abs: str, name: str) -> str:
    full = os.path.join(base_abs, name)
    try:
        st = os.stat(full)
    except Exception:
        return f"? {'?'*10} {'?'*16} {name}"
    tchar = "d" if stat.S_ISDIR(st.st_mode) else "-"
    size = st.st_size
    mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime))
    shown = name + ("/" if stat.S_ISDIR(st.st_mode) else "")
    return f"{tchar} {size:>10} {mtime} {shown}"




def execute_command(line: str) -> str:
    global current_directory

    try:
        command, arg = get_current_line_command(line)
    except ValueError as e:
        return str(e) + "\n"

    if not command:
        return ""

    if command not in ListOfCommands:
        return f"Command not found: {command}"

    if command == "exit":
        root.destroy()
        return ""

    if command == "pwd":
        return "/" if not current_directory else "/" + current_directory

    if command == "cd":
        directory = arg if arg else "/"
        if directory and directory[0] == "~":
             directory = "/" + directory[1:]
        new_path = make_path_vfs(directory)
        if not os.path.isdir(new_path):
            return f"No such directory: cd: {path_rel_to_vfs(new_path)}"
        rel = os.path.relpath(new_path, vfs_root).replace("\\", "/")
        current_directory = "" if rel in (".", "") else rel
        return ""

    if command == "ls":
        flags, paths, err = parse_ls_args(arg)
        if err:
            return err + "\n"

        outputs = []
        multiple = len(paths) > 1

        for p in paths:
            abs_path = make_path_vfs(p)
            if not os.path.exists(abs_path):
                outputs.append(f"ls: cannot access '{p}': No such file or directory")
                continue

            if os.path.isdir(abs_path):
                try:
                    items = os.listdir(abs_path)
                except Exception as e:
                    outputs.append(f"ls: {p}: {e}")
                    continue

                items_sorted = sorted(items, reverse=("r" in flags))
                if "l" in flags:
                    lines = [format_long_entry(abs_path, name) for name in items_sorted]
                else:
                    lines = [mark_dirname(abs_path, name) for name in items_sorted]

                block = "\n".join(lines) if lines else ""
                if multiple:
                    outputs.append(f"{path_rel_to_vfs(abs_path)}:\n{block}")
                else:
                    outputs.append(block)
            else:
                base = os.path.dirname(abs_path) or vfs_root
                name = os.path.basename(abs_path)
                line_out = format_long_entry(base, name) if "l" in flags else mark_dirname(base, name)
                outputs.append(line_out)

        return ("\n\n".join(outputs) + ("\n" if outputs else ""))

    return ""



def append_output_and_prompt(output: str):
    global prompt
    # если последним символом не \n — перенесёмся на новую строку
    try:
        last = console.get("end-2c", "end-1c")
    except tk.TclError:
        last = ""
    if last != "\n":
        console.insert("end", "\n")

    # вывод команды (без добавочной пустой строки)
    if output:
        if not output.endswith("\n"):
            output += "\n"
        console.insert("end", output)

    # новый промпт сразу после вывода
    prompt = make_prompt()
    console.insert("end", prompt)
    console.see("end")
    console.mark_set("insert", "end")


def run_command(event=None):
    global prompt
    line_start = console.index("insert linestart")
    user_line = console.get(f"{line_start}+{len(prompt)}c", f"{line_start} lineend")

    output = execute_command(user_line);
    try:
        append_output_and_prompt(output)
    except tk.TclError:
        pass
    return "break"

def protect_prompt(event):
    if event.keysym == "Return":
        return
    if event.keysym in ("Left", "Right", "Up", "Down", "End", "Next", "Prior",
                        "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R"):
        if event.keysym == "Home":
            line_start = console.index("insert linestart")
            console.mark_set("insert", f"{line_start}+{len(prompt)}c")
            return "break"
        return


    line_start = console.index("insert linestart")
    guard = console.index(f"{line_start}+{len(prompt)}c")
    idx = console.index("insert")


    if console.compare(idx, "<=", guard):
        console.mark_set("insert", guard)

    if event.keysym == "BackSpace":
        idx = console.index("insert")
        if console.compare(idx, "<=", guard):
            return "break"

    if event.keysym == "Delete":
        next_idx = console.index("insert +1c")
        if console.compare(next_idx, "<=", guard):
            return "break"

console.bind("<Return>", run_command)
console.bind("<Key>", protect_prompt)



def run_start_script_if_needed():
    if not args.script:
        return
    script_path = os.path.abspath(args.script)
    if not os.path.isfile(script_path):
        output_text(f"[warn] Starting script is not found: {script_path}")
        return

    try:
        with open(script_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        output_text(f"[warn] Caт not read the script: {e}")
        return

    for string in lines:
        line = string.rstrip("\r\n")
        if not line or line.lstrip().startswith("#"):
            continue

        output_to_console(make_prompt())
        output_text(line)
        try:
            out = execute_command(line)
        except Exception as e:
            out = f"[skip] Error of line execution: {e}\n"
        try:
            append_output_and_prompt(out)
        except tk.TclError:
            break

root.after(50, run_start_script_if_needed)

root.mainloop()