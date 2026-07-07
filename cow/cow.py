import re
import sys
from collections import defaultdict

COMMANDS = ["moo", "mOo", "moO", "mOO", "Moo", "MOo", "MoO", "MOO", "OOO", "MMM", "OOM", "oom"]
TOKEN_RE = re.compile("|".join(COMMANDS))


def tokenize(source):
    source = re.sub(r"//[^\n]*", "", source)
    return TOKEN_RE.findall(source)


def match_loops(prog):
    jumps = {}
    stack = []
    for i, cmd in enumerate(prog):
        if cmd == "MOO":
            stack.append(i)
        elif cmd == "moo":
            if not stack:
                sys.exit(f"unmatched 'moo' at command {i}")
            start = stack.pop()
            jumps[start] = i
            jumps[i] = start
    if stack:
        sys.exit(f"unmatched 'MOO' at command {stack[-1]}")
    return jumps


def read_int():
    token = []
    while True:
        ch = sys.stdin.read(1)
        if not ch:
            break
        if ch.isspace():
            if token:
                break
            continue
        token.append(ch)
    if not token:
        sys.exit("ran out of input for 'oom'")
    return int("".join(token))


def run(prog):
    jumps = match_loops(prog)
    tape = defaultdict(int)
    ptr = 0
    register = None
    printed = False
    pc = 0
    while pc < len(prog):
        cmd = prog[pc]
        if cmd == "mOo":
            ptr -= 1
        elif cmd == "moO":
            ptr += 1
        elif cmd == "MoO":
            tape[ptr] += 1
        elif cmd == "MOo":
            tape[ptr] -= 1
        elif cmd == "OOO":
            tape[ptr] = 0
        elif cmd == "MMM":
            if register is None:
                register = tape[ptr]
            else:
                tape[ptr] = register
                register = None
        elif cmd == "Moo":
            if tape[ptr] == 0:
                ch = sys.stdin.read(1)
                tape[ptr] = ord(ch) if ch else 0
            else:
                sys.stdout.write(chr(tape[ptr]))
                sys.stdout.flush()
                printed = True
        elif cmd == "OOM":
            sys.stdout.write(str(tape[ptr]))
            sys.stdout.flush()
            printed = True
        elif cmd == "oom":
            tape[ptr] = read_int()
        elif cmd == "mOO":
            value = tape[ptr]
            if not 0 <= value <= 11 or value in (0, 3, 7):
                sys.exit(f"'mOO' cannot execute cell value {value}")
            prog = prog[:pc] + [COMMANDS[value]] + prog[pc + 1 :]
            continue
        elif cmd == "MOO":
            if tape[ptr] == 0:
                pc = jumps[pc]
        elif cmd == "moo":
            pc = jumps[pc] - 1
        pc += 1
    if printed:
        sys.stdout.write("\n")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python cow.py <program.cow>")
    with open(sys.argv[1], encoding="utf-8") as f:
        run(tokenize(f.read()))
