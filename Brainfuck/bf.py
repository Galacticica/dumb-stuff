import sys


def run(code: str) -> None:
    jumps = {}
    stack = []
    for i, c in enumerate(code):
        if c == "[":
            stack.append(i)
        elif c == "]":
            start = stack.pop()
            jumps[start] = i
            jumps[i] = start
    if stack:
        sys.exit(f"unmatched '[' at position {stack[-1]}")

    tape = bytearray(30000)
    ptr = 0
    pc = 0
    while pc < len(code):
        c = code[pc]
        if c == ">":
            ptr += 1
        elif c == "<":
            ptr -= 1
        elif c == "+":
            tape[ptr] = (tape[ptr] + 1) % 256
        elif c == "-":
            tape[ptr] = (tape[ptr] - 1) % 256
        elif c == ".":
            sys.stdout.buffer.write(bytes([tape[ptr]]))
            sys.stdout.buffer.flush()
        elif c == ",":
            byte = sys.stdin.buffer.read(1)
            tape[ptr] = byte[0] if byte else 0
        elif c == "[" and tape[ptr] == 0:
            pc = jumps[pc]
        elif c == "]" and tape[ptr] != 0:
            pc = jumps[pc]
        pc += 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python bf.py <program.bf>")
    with open(sys.argv[1]) as f:
        run(f.read())
