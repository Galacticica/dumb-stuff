import sys

# Whitespace interpreter. Only space, tab, and linefeed are significant;
# every other byte is a comment and ignored.
S, T, L = " ", "\t", "\n"


class WSError(Exception):
    pass


def tokenize(source):
    return [c for c in source if c in (S, T, L)]


class Parser:
    def __init__(self, tokens):
        self.toks = tokens
        self.i = 0

    def next(self):
        if self.i >= len(self.toks):
            raise WSError("unexpected end of program")
        c = self.toks[self.i]
        self.i += 1
        return c

    def at_end(self):
        return self.i >= len(self.toks)

    def read_number(self):
        # sign then binary digits (space=0, tab=1) then linefeed
        sign = self.next()
        if sign == L:
            raise WSError("number with no digits")
        bits = []
        while True:
            c = self.next()
            if c == L:
                break
            bits.append("0" if c == S else "1")
        value = int("".join(bits), 2) if bits else 0
        return -value if sign == T else value

    def read_label(self):
        # a run of space/tab terminated by linefeed; keep as a string key
        label = []
        while True:
            c = self.next()
            if c == L:
                break
            label.append(c)
        return "".join(label)


def parse(tokens):
    p = Parser(tokens)
    program = []  # list of (op, arg)
    while not p.at_end():
        imp = p.next()
        if imp == S:  # stack manipulation
            c = p.next()
            if c == S:
                program.append(("push", p.read_number()))
            elif c == T:
                c2 = p.next()
                if c2 == S:
                    program.append(("copy", p.read_number()))
                elif c2 == L:
                    program.append(("slide", p.read_number()))
                else:
                    raise WSError("bad stack instruction")
            else:  # L
                c2 = p.next()
                if c2 == S:
                    program.append(("dup", None))
                elif c2 == T:
                    program.append(("swap", None))
                else:
                    program.append(("discard", None))
        elif imp == T:
            c = p.next()
            if c == S:  # arithmetic
                a, b = p.next(), p.next()
                op = {
                    (S, S): "add", (S, T): "sub", (S, L): "mul",
                    (T, S): "div", (T, T): "mod",
                }.get((a, b))
                if op is None:
                    raise WSError("bad arithmetic instruction")
                program.append((op, None))
            elif c == T:  # heap access
                c2 = p.next()
                program.append(("store" if c2 == S else "retrieve", None))
            else:  # T L : I/O
                a, b = p.next(), p.next()
                op = {
                    (S, S): "ochr", (S, T): "onum",
                    (T, S): "ichr", (T, T): "inum",
                }.get((a, b))
                if op is None:
                    raise WSError("bad I/O instruction")
                program.append((op, None))
        else:  # L : flow control
            a, b = p.next(), p.next()
            if (a, b) == (S, S):
                program.append(("label", p.read_label()))
            elif (a, b) == (S, T):
                program.append(("call", p.read_label()))
            elif (a, b) == (S, L):
                program.append(("jmp", p.read_label()))
            elif (a, b) == (T, S):
                program.append(("jz", p.read_label()))
            elif (a, b) == (T, T):
                program.append(("jn", p.read_label()))
            elif (a, b) == (T, L):
                program.append(("ret", None))
            elif (a, b) == (L, L):
                program.append(("end", None))
            else:
                raise WSError("bad flow-control instruction")
    return program


def run(program):
    labels = {}
    for idx, (op, arg) in enumerate(program):
        if op == "label":
            if arg in labels:
                raise WSError(f"duplicate label")
            labels[arg] = idx

    stack = []
    heap = {}
    call_stack = []
    pc = 0

    def pop():
        if not stack:
            raise WSError("pop from empty stack")
        return stack.pop()

    while pc < len(program):
        op, arg = program[pc]
        if op == "push":
            stack.append(arg)
        elif op == "dup":
            stack.append(stack[-1])
        elif op == "copy":
            stack.append(stack[-(arg + 1)])
        elif op == "swap":
            stack[-1], stack[-2] = stack[-2], stack[-1]
        elif op == "discard":
            pop()
        elif op == "slide":
            top = pop()
            del stack[len(stack) - arg:]
            stack.append(top)
        elif op in ("add", "sub", "mul", "div", "mod"):
            b, a = pop(), pop()
            if op == "add":
                stack.append(a + b)
            elif op == "sub":
                stack.append(a - b)
            elif op == "mul":
                stack.append(a * b)
            elif op == "div":
                if b == 0:
                    raise WSError("division by zero")
                stack.append(a // b)  # floored, per the reference implementation
            else:
                if b == 0:
                    raise WSError("modulo by zero")
                stack.append(a % b)
        elif op == "store":
            value, addr = pop(), pop()
            heap[addr] = value
        elif op == "retrieve":
            stack.append(heap.get(pop(), 0))
        elif op == "ochr":
            sys.stdout.write(chr(pop()))
            sys.stdout.flush()
        elif op == "onum":
            sys.stdout.write(str(pop()))
            sys.stdout.flush()
        elif op == "ichr":
            ch = sys.stdin.read(1)
            heap[pop()] = ord(ch) if ch else -1
        elif op == "inum":
            line = sys.stdin.readline()
            heap[pop()] = int(line.strip())
        elif op == "label":
            pass
        elif op == "call":
            call_stack.append(pc)
            pc = labels[arg]
        elif op == "jmp":
            pc = labels[arg]
        elif op == "jz":
            if pop() == 0:
                pc = labels[arg]
        elif op == "jn":
            if pop() < 0:
                pc = labels[arg]
        elif op == "ret":
            if not call_stack:
                raise WSError("return with empty call stack")
            pc = call_stack.pop()
        elif op == "end":
            return
        pc += 1


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python whitespace.py <program.ws>")
    with open(sys.argv[1], encoding="utf-8", errors="replace") as f:
        source = f.read()
    try:
        run(parse(tokenize(source)))
    except WSError as e:
        sys.exit(f"whitespace error: {e}")


if __name__ == "__main__":
    main()
