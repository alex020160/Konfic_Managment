# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import scrolledtext
import sys, io, os, shlex, getpass, socket

username = getpass.getuser()
hostname = socket.gethostname()

def make_prompt() -> str:
    return f"[{username}@{hostname}]:~# "

ListOfCommands = {"exit", "ls", "cd"}

root = tk.Tk()
root.title(f"Эмулятор - [{username}@{hostname}]")

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

def get_current_line_command(line: str):
    try:
        input = shlex.split(line)
    except ValueError as e:
        raise ValueError(f"Ошибка парсинга: {e}")
    if not input:
        return "", ""
    command = input[0]
    arg = " ".join(input[1:]) if len(input) > 1 else ""
    return command, arg

def run_command(event=None):
    global prompt

    line_start = console.index("insert linestart");
    user_line = console.get(f"{line_start}+{len(prompt)}c", f"{line_start} lineend")

    try:
        command, arg = get_current_line_command(user_line)
    except ValueError as e:
        console.insert("end", f"\n{e}\n{make_prompt()}")
        console.see("end")
        console.mark_set("insert", "end")
        return "break"

    if not command:
        console.insert("end", "\n" + make_prompt())
        console.see("end")
        console.mark_set("insert", "end")
        return "break"

    output = ""
    if command not in ListOfCommands:
        output = f"{command}: command not found\n"
    elif command == "exit":
        root.destroy();
    elif command == "ls":
        try:
            output = "Nothing right now - command ls\n";
        except Exception as e:
            output = f"ls: {e}\n"
    elif command == "cd":
        try:
            output = "Nothing right now - command cd\n";
        except Exception as e:
            output = f"cd: {e}\n"
    prompt = make_prompt()
    if output and not output.endswith("\n"):
        output += "\n"
    console.insert("end", "\n" + output + prompt)
    console.see("end")
    console.mark_set("insert", "end")
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

root.mainloop()
