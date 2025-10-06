# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import scrolledtext
import sys, os, shlex, getpass, socket, argparse, json, base64, platform, re

#этап2
parser = argparse.ArgumentParser(
    description="GUI emulator with in-memory VFS (from JSON) and startup script"
)
parser.add_argument(
    "--vfs-json", required=True, help="Path to JSON file describing the in-memory VFS"
)
parser.add_argument(
    "--script", type=str, default=None, help="Path to startup command script (optional)"
)
args = parser.parse_args()


#этап5
def _as_mode(m):
    if isinstance(m, int):
        return m
    if isinstance(m, str):
        # "644" / "0644" → как восьмеричное
        return int(m, 8)
    return None


#этап3
def wrap_any_json_to_vfs(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    def to_vfs(name, obj):
        if isinstance(obj, dict):
            children = [to_vfs(k, v) for k, v in obj.items()]
            return {"type": "dir", "name": name, "children": children}
        elif isinstance(obj, list):
            children = [to_vfs(f"item_{i}", v) for i, v in enumerate(obj)]
            return {"type": "dir", "name": name, "children": children}
        else:
            return {
                "type": "file",
                "name": f"{name}.txt",
                "encoding": "text",
                "content": str(obj),
            }

    vfs = {
        "type": "dir",
        "name": "/",
        "children": [to_vfs(k, v) for k, v in data.items()],
    }
    return vfs


# этап3
class VFSLoadError(Exception):
    pass



#этап3
class VFSNode:
    def __init__(self, name, mode: int | None = None):
        self.name = name
        self.mode = mode if mode is not None else 0o644

        
#этап3
class VFSDir(VFSNode):
    def __init__(self, name, mode: int | None = None):
        super().__init__(name, mode if mode is not None else 0o755)
        self.children = {}  # name -> node
    def add(self, node):
        if "/" in node.name or node.name in (".", "..") or not node.name:
            raise VFSLoadError(f"Invalid name for node: {node.name!r}")
        if node.name in self.children:
            raise VFSLoadError(f"Duplicate entry: {node.name!r}")
        self.children[node.name] = node


 #этап3
class VFSFile(VFSNode):
    def __init__(self, name, encoding, content_bytes, mode: int | None = None):
        super().__init__(name, mode if mode is not None else 0o644)
        self.encoding = encoding
        self.content = content_bytes



#этап3
def _ensure(obj, key, typ):
    if key not in obj:
        raise VFSLoadError(f"Missing key: {key}")
    if not isinstance(obj[key], typ):
        raise VFSLoadError(f"Key {key} has wrong type, expected {typ.__name__}")
    return obj[key]


#этап3
def load_vfs_from_json(path):
    if os.path.isdir(path):
        raise VFSLoadError(f"Expected JSON file, but got a directory: {path}")
    # читаем json
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise VFSLoadError(f"VFS file not found: {path}")
    except json.JSONDecodeError as e:
        raise VFSLoadError(f"Invalid JSON: {e}")

    # собираем дерево
    #этап3
    def build(node_obj, expected_root=False):
        typ = _ensure(node_obj, "type", str)
        name = _ensure(node_obj, "name", str)
        mode = _as_mode(node_obj.get("mode"))

        if expected_root and name != "/":
            raise VFSLoadError('Root node name must be "/"')

        if typ == "dir":
            dirnode = VFSDir(name if not expected_root else "/", mode)
            children = _ensure(node_obj, "children", list)
            for child in children:
                dirnode.add(build(child))
            return dirnode
        elif typ == "file":
            encoding = _ensure(node_obj, "encoding", str)
            content = _ensure(node_obj, "content", str)
            if encoding == "text":
                content_bytes = content.encode("utf-8", errors="replace")
            elif encoding == "base64":
                try:
                    content_bytes = base64.b64decode(content, validate=True)
                except Exception as e:
                    raise VFSLoadError(f"base64 decode failed for {name!r}: {e}")
            else:
                raise VFSLoadError(f"Unknown file encoding {encoding!r} for {name!r}")
            return VFSFile(name, encoding, content_bytes, mode)
        else:
            raise VFSLoadError(f"Unknown node type {typ!r} for {name!r}")

    try:
        root = build(data, expected_root=True)
        if not isinstance(root, VFSDir):
            raise VFSLoadError("Root must be directory")
    except VFSLoadError:
        raise
    except Exception as e:
        raise VFSLoadError(f"Invalid VFS structure: {e}")

    return root



#этап3
try:
    VFS_ROOT = load_vfs_from_json(args.vfs_json)
except VFSLoadError as e:
    print(f"[VFS load] {e}", file=sys.stderr)
    print("[info] Файл не VFS-формата, конвертирую произвольный JSON в дерево", file=sys.stderr)
    wrapped = wrap_any_json_to_vfs(args.vfs_json)
    tmp = "._tmp_vfs.json"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(wrapped, f, ensure_ascii=False)
    VFS_ROOT = load_vfs_from_json(tmp)

# директория - список компонентов (['/'] = корень)
#этап 3
CWD = []  # пустой список = "/"


#этап3
def cwd_str():
    return "/" if not CWD else "/" + "/".join(CWD)


#этап3
def _split_path(p):
    """Разобрать строковый путь на компоненты без пустых и '.'; '..' обрабатываем отдельно."""
    comps = [c for c in p.split("/") if c not in ("", ".")]
    return comps


#этап5
def _mode_to_rwx(mode: int, is_dir: bool) -> str:
    # тип: d/-
    t = "d" if is_dir else "-"
    # rwx-блоки
    bits = [(mode >> 6) & 7, (mode >> 3) & 7, mode & 7]
    s = ""
    for b in bits:
        s += "r" if (b & 4) else "-"
        s += "w" if (b & 2) else "-"
        s += "x" if (b & 1) else "-"
    return t + s


#этап3
def _resolve(path_str, must_be_dir=None):
    """
    Разрешить путь и вернуть (node, normalized_components_list).
    path_str может быть абсолютным или относительным.
    must_be_dir: None/True/False — требование для конечного узла.
    """
    if path_str.startswith("/"):
        comps = []
        rest = _split_path(path_str)
    else:
        comps = list(CWD)
        rest = _split_path(path_str)

    node = VFS_ROOT
    # пройти по comps (текущая база)
    for c in comps:
        if not isinstance(node, VFSDir):
            raise FileNotFoundError("Not a directory in path head")
        if c not in node.children or not isinstance(node.children[c], VFSDir):
            raise FileNotFoundError(f"No such directory: /{'/'.join(comps)}")
        node = node.children[c]

    # применить rest, учитывая '..'
    for c in rest:
        if c == "..":
            if comps:
                comps.pop()
                node = VFS_ROOT
                for cc in comps:
                    node = node.children[cc]
            else:
                node = VFS_ROOT
        else:
            if not isinstance(node, VFSDir):
                raise FileNotFoundError("Not a directory in path walk")
            if c not in node.children:
                raise FileNotFoundError(f"No such entry: {cwd_str()}/{c}" if CWD else f"No such entry: /{c}")
            node = node.children[c]
            comps.append(c)

    if must_be_dir is True and not isinstance(node, VFSDir):
        raise NotADirectoryError(f"Not a directory: /{'/'.join(comps) if comps else ''}")
    if must_be_dir is False and isinstance(node, VFSDir):
        raise IsADirectoryError(f"Is a directory: /{'/'.join(comps) if comps else ''}")
    return node, comps

#этап1
username = getpass.getuser()
hostname = socket.gethostname()

#этап1
def make_prompt() -> str:
    return f"[{username}@{hostname} {cwd_str()}]# "

#этапы1-5
COMMANDS = {"exit", "ls", "cd", "pwd", "cat", "head", "uname", "chmod"}


#этап1
root = tk.Tk()
root.title(f"Emulator - [{username}@{hostname}]")

console = scrolledtext.ScrolledText(
    root,
    width=100,
    height=28,
    font=("Consolas", 12),
    fg="black",
    bg="white",
    insertbackground="black",
    wrap="none",
)
console.pack(padx=10, pady=10)

#этап 1
def write(text: str, end: str = ""):
    console.insert("end", text + end)
    console.see("end")

#этап 1
def writeln(text: str = ""):
    write(text + "\n")


# Отладка параметров - этап 2
writeln("=== debug: startup parameters ===")
writeln(f"--vfs-json = {os.path.abspath(args.vfs_json)}")
writeln(f"--script   = {args.script if args.script else '(no script)'}")
writeln("=================================")

prompt = make_prompt()
console.insert("end", prompt)
guard_index = console.index(f"end-1c - {len(prompt)}c")
console.mark_set("insert", f"{guard_index}+{len(prompt)}c")
console.focus_set()

#этап 1 - парсер
def parse_line(line: str):
    try:
        parts = shlex.split(line)
    except ValueError as e:
        raise ValueError(f"Parse error: {e}")
    if not parts:
        return "", ""
    cmd = parts[0]
    arg = " ".join(parts[1:]) if len(parts) > 1 else ""
    return cmd, arg

#этап 4
def do_head(arg: str) -> str:
    if not arg:
        return "head: path required\n"
    parts = shlex.split(arg)
    n = 10
    path = None
    i = 0
    while i < len(parts):
        if parts[i] in ("-n", "--lines"):
            i += 1
            if i >= len(parts):
                return "head: missing number after -n\n"
            try:
                n = int(parts[i])
            except ValueError:
                return "head: invalid number\n"
        else:
            path = parts[i]
        i += 1
    if not path:
        return "head: path required\n"

    try:
        node, _ = _resolve(path, must_be_dir=False)
        if isinstance(node, VFSDir):
            return "head: is a directory\n"
        text = node.content.decode("utf-8", errors="replace").splitlines()
        out = "\n".join(text[:max(n, 0)])
        if out and not out.endswith("\n"):
            out += "\n"
        return out
    except Exception as e:
        return f"head: {e}\n"

#этап 4
def do_uname(arg: str) -> str:
    s = platform.system()
    n = socket.gethostname()
    r = platform.release()
    v = platform.version()
    m = platform.machine()

    flags = set(shlex.split(arg)) if arg else set()
    if not flags or "-a" in flags:
        return f"{s} {n} {r} {v} {m}\n"

    out = []
    if "-s" in flags:
        out.append(s)
    if "-n" in flags:
        out.append(n)
    if "-r" in flags:
        out.append(r)
    if "-v" in flags:
        out.append(v)
    if "-m" in flags:
        out.append(m)
    return (" ".join(out) + "\n") if out else (s + "\n")

#этап 5
def _parse_octal_mode(s: str) -> int | None:
    # допускаем "755", "0755", "644"
    if not re.fullmatch(r"0?[0-7]{3}", s):
        return None
    return int(s, 8)


#этап 5
def do_chmod(arg: str) -> str:
    if not arg:
        return "chmod: usage: chmod MODE PATH\n"
    parts = shlex.split(arg)
    if len(parts) < 2:
        return "chmod: usage: chmod MODE PATH\n"
    mode_str, path = parts[0], parts[1]
    mode = _parse_octal_mode(mode_str)
    if mode is None:
        return f"chmod: invalid mode: {mode_str}\n"
    try:
        node, _ = _resolve(path, must_be_dir=None)
        node.mode = mode
        return ""
    except Exception as e:
        return f"chmod: {e}\n"

#этап 4
def do_ls(arg: str) -> str:
    show_long = False
    target = "."
    if arg:
        parts = shlex.split(arg)
        for p in parts:
            if p == "-l":
                show_long = True
            else:
                target = p
    try:
        node, _ = _resolve(target, must_be_dir=True)
    except Exception as e:
        return f"ls: {e}\n"

    lines = []
    for name, child in sorted(node.children.items(), key=lambda kv: kv[0].lower()):
        display = name + ("/" if isinstance(child, VFSDir) else "")
        if show_long:
            is_dir = isinstance(child, VFSDir)
            perm = _mode_to_rwx(child.mode, is_dir)
            size = len(child.content) if isinstance(child, VFSFile) else 0
            lines.append(f"{perm}   user   {size:>6}  {display}")
        else:
            lines.append(display)
    return ("\n".join(lines) + ("\n" if lines else ""))

#этап 4
def do_cd(arg: str) -> str:
    global CWD
    target = arg if arg else "/"
    try:
        _, comps = _resolve(target, must_be_dir=True)
        CWD = comps  # меняем текущую директорию
        return ""
    except Exception as e:
        return f"cd: {e}\n"

#этап 3
def do_pwd() -> str:
    return cwd_str() + "\n"

#этап 3
def do_cat(arg: str) -> str:
    if not arg:
        return "cat: path required\n"
    try:
        node, _ = _resolve(arg, must_be_dir=False)
        if isinstance(node, VFSDir):
            return "cat: is a directory\n"
        if node.encoding == "text":
            try:
                return node.content.decode("utf-8", errors="replace") + (
                    "\n" if not node.content.endswith(b"\n") else ""
                )
            except Exception:
                return node.content.decode("utf-8", errors="replace")
        else:
            b = node.content
            n = len(b)
            preview = b[:64].hex(" ")
            return (
                f"[binary file] {node.name} ({n} bytes)\n"
                f"hex preview (first 64B):\n{preview}\n"
            )
    except Exception as e:
        return f"cat: No such entry {e}\n"

#этапы 1-5
def execute(line: str) -> str:
    try:
        cmd, arg = parse_line(line)
    except ValueError as e:
        return str(e) + "\n"
    if not cmd:
        return ""
    if cmd not in COMMANDS:
        return f"{cmd}: command not found\n"
    if cmd == "exit":
        root.after(0, root.destroy)
        return ""
    if cmd == "ls":
        return do_ls(arg)
    if cmd == "cd":
        return do_cd(arg)
    if cmd == "pwd":
        return do_pwd()
    if cmd == "cat":
        return do_cat(arg)
    if cmd == "head":
        return do_head(arg)
    if cmd == "uname":
        return do_uname(arg)
    if cmd == "chmod":
        return do_chmod(arg)
    return ""

#этап 1
def append_output_and_prompt(output: str):
    global prompt
    if output and not output.endswith("\n"):
        output += "\n"
    prompt = make_prompt()
    console.insert("end", (output or "") + prompt)
    console.see("end")
    console.mark_set("insert", "end")

#этап 1
def on_enter(event=None):
    global prompt
    line_start = console.index("insert linestart")
    user_line = console.get(f"{line_start}+{len(prompt)}c", f"{line_start} lineend")

    out = execute(user_line)

    #перенос строки между командой и её выводом
    console.insert("end", "\n")

    try:
        append_output_and_prompt(out)  
    except tk.TclError:
        pass
    return "break"


#этап 1
def protect_prompt(event):
    if event.keysym == "Return":
        return
    if event.keysym in (
        "Left",
        "Right",
        "Up",
        "Down",
        "End",
        "Next",
        "Prior",
        "Shift_L",
        "Shift_R",
        "Control_L",
        "Control_R",
        "Alt_L",
        "Alt_R",
    ):
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
        if console.compare(console.index("insert"), "<=", guard):
            return "break"

    if event.keysym == "Delete":
        next_idx = console.index("insert +1c")
        if console.compare(next_idx, "<=", guard):
            return "break"

#этап 1
console.bind("<Return>", on_enter)
console.bind("<Key>", protect_prompt)

#этап 2
def run_start_script_if_needed():
    if not args.script:
        return
    script_path = os.path.abspath(args.script)
    if not os.path.isfile(script_path):
        writeln(f"[warn] Starting script is not found: {script_path}")
        return
    try:
        with open(script_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        writeln(f"[warn] Cannot read script: {e}")
        return

    for raw in lines:
        line = raw.rstrip("\r\n")
        if not line or line.lstrip().startswith("#"):
            continue
        write(make_prompt())
        writeln(line)
        try:
            out = execute(line)
        except Exception as e:
            out = f"[skip] execution error: {e}\n"
        try:
            append_output_and_prompt(out)
        except tk.TclError:
            break

#этап 1,2
root.after(50, run_start_script_if_needed)
root.mainloop()
