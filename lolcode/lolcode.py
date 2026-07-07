import re
import sys

INT_RE = re.compile(r"-?\d+$")
FLOAT_RE = re.compile(r"-?\d+\.\d+$")
TYPES = ("NOOB", "TROOF", "NUMBR", "NUMBAR", "YARN")


class LolError(Exception):
    pass


class LolBreak(Exception):
    pass


class LolReturn(Exception):
    def __init__(self, value):
        self.value = value


# ---------------------------------------------------------------- tokenizing

def tokenize(source):
    """Return a list of statements; each statement is a list of tokens.
    A token is ("str", text) or ("word", text). Commas split statements."""
    statements = []
    current = []
    in_obtw = False
    lines = source.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if in_obtw:
            if "TLDR" in line.split():
                in_obtw = False
            continue
        stripped = line.strip()
        if stripped.startswith("OBTW"):
            in_obtw = True
            continue
        # join continuation lines ending with an ellipsis
        while stripped.endswith(("…", "...")) and i < len(lines):
            stripped = stripped.rstrip(".…").strip() + " " + lines[i].strip()
            i += 1
        for token in scan_line(stripped):
            if token == ("word", ","):
                if current:
                    statements.append(current)
                    current = []
            else:
                current.append(token)
        if current:
            statements.append(current)
            current = []
    return statements


def scan_line(line):
    tokens = []
    pos = 0
    n = len(line)
    while pos < n:
        ch = line[pos]
        if ch.isspace():
            pos += 1
        elif ch == ",":
            tokens.append(("word", ","))
            pos += 1
        elif ch == '"':
            pos += 1
            buf = []
            while pos < n and line[pos] != '"':
                if line[pos] == ":" and pos + 1 < n:
                    esc = line[pos + 1]
                    if esc == ")":
                        buf.append("\n")
                        pos += 2
                    elif esc == ">":
                        buf.append("\t")
                        pos += 2
                    elif esc == "o":
                        buf.append("\a")
                        pos += 2
                    elif esc == "{":
                        end = line.index("}", pos)
                        buf.append("\x00" + line[pos + 2 : end] + "\x00")
                        pos = end + 1
                    elif esc == '"' and '"' not in line[pos + 2 :]:
                        # lenient: a :" with no later closing quote is a plain
                        # colon followed by the end of the string
                        buf.append(":")
                        pos += 1
                    else:  # :" :: and anything else escapes the next char
                        buf.append(esc)
                        pos += 2
                else:
                    buf.append(line[pos])
                    pos += 1
            pos += 1
            tokens.append(("str", "".join(buf)))
        else:
            end = pos
            while end < n and not line[end].isspace() and line[end] not in ',"':
                end += 1
            word = line[pos:end]
            pos = end
            if word == "BTW":
                break
            tokens.append(("word", word))
    return tokens


# ---------------------------------------------------------------- values

def truthy(v):
    return not (v is None or v is False or v == 0 or v == "")


def to_num(v):
    if isinstance(v, bool):
        return 1 if v else 0
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        s = v.strip()
        if INT_RE.match(s):
            return int(s)
        if FLOAT_RE.match(s):
            return float(s)
        raise LolError(f"cannot use YARN '{v}' as a number")
    raise LolError("cannot use NOOB as a number")


def to_str(v):
    if v is None:
        return "NOOB"
    if isinstance(v, bool):
        return "WIN" if v else "FAIL"
    if isinstance(v, float):
        return format(v, ".10g")
    return str(v)


def same(a, b):
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, (int, float)) or isinstance(b, (int, float)):
        try:
            return to_num(a) == to_num(b)
        except LolError:
            return False
    return a == b


def cast(v, type_name):
    if type_name == "NOOB":
        return None
    if type_name == "TROOF":
        return truthy(v)
    if type_name == "NUMBR":
        return int(to_num(v))
    if type_name == "NUMBAR":
        return float(to_num(v))
    if type_name == "YARN":
        return to_str(v)
    raise LolError(f"unknown type '{type_name}'")


# ---------------------------------------------------------------- parsing

class Interpreter:
    def __init__(self, statements):
        self.stmts = statements
        self.pos = 0
        self.funcs = {}

    # --- statement stream helpers

    def words(self, stmt):
        return [text if kind == "word" else '"' for kind, text in stmt]

    def next_starts_with(self, *prefix):
        if self.pos >= len(self.stmts):
            return False
        w = self.words(self.stmts[self.pos])
        return tuple(w[: len(prefix)]) == prefix

    def parse_block(self, stop_prefixes):
        block = []
        while self.pos < len(self.stmts):
            for prefix in stop_prefixes:
                if self.next_starts_with(*prefix):
                    return block
            block.append(self.parse_stmt())
        return block

    # --- expressions: parse token list, return (closure, next_index)

    def parse_expr(self, t, i):
        if i >= len(t):
            raise LolError("expected an expression")
        kind, text = t[i]
        if kind == "str":
            return (lambda env: interp_yarn(text, env)), i + 1
        if text in ("SUM", "DIFF", "PRODUKT", "QUOSHUNT", "MOD", "BIGGR", "SMALLR"):
            self.expect(t, i + 1, "OF")
            a, i = self.parse_expr(t, i + 2)
            i = self.skip(t, i, "AN")
            b, i = self.parse_expr(t, i)
            op = text
            return (lambda env: math_op(op, a(env), b(env))), i
        if text == "BOTH" and self.peek(t, i + 1) == "SAEM":
            a, i = self.parse_expr(t, i + 2)
            i = self.skip(t, i, "AN")
            b, i = self.parse_expr(t, i)
            return (lambda env: same(a(env), b(env))), i
        if text == "DIFFRINT":
            a, i = self.parse_expr(t, i + 1)
            i = self.skip(t, i, "AN")
            b, i = self.parse_expr(t, i)
            return (lambda env: not same(a(env), b(env))), i
        if text in ("BOTH", "EITHER", "WON"):
            self.expect(t, i + 1, "OF")
            a, i = self.parse_expr(t, i + 2)
            i = self.skip(t, i, "AN")
            b, i = self.parse_expr(t, i)
            op = text
            return (
                lambda env: truthy(a(env)) and truthy(b(env))
                if op == "BOTH"
                else truthy(a(env)) or truthy(b(env))
                if op == "EITHER"
                else truthy(a(env)) != truthy(b(env))
            ), i
        if text == "NOT":
            a, i = self.parse_expr(t, i + 1)
            return (lambda env: not truthy(a(env))), i
        if text in ("ALL", "ANY"):
            self.expect(t, i + 1, "OF")
            i += 2
            parts = []
            while i < len(t) and self.peek(t, i) != "MKAY":
                i = self.skip(t, i, "AN")
                e, i = self.parse_expr(t, i)
                parts.append(e)
            i = self.skip(t, i, "MKAY")
            fn = all if text == "ALL" else any
            return (lambda env: fn(truthy(p(env)) for p in parts)), i
        if text == "SMOOSH":
            i += 1
            parts = []
            while i < len(t) and self.peek(t, i) != "MKAY":
                i = self.skip(t, i, "AN")
                e, i = self.parse_expr(t, i)
                parts.append(e)
            i = self.skip(t, i, "MKAY")
            return (lambda env: "".join(to_str(p(env)) for p in parts)), i
        if text == "MAEK":
            a, i = self.parse_expr(t, i + 1)
            i = self.skip(t, i, "A")
            type_name = self.peek(t, i)
            return (lambda env: cast(a(env), type_name)), i + 1
        if text == "I" and self.peek(t, i + 1) == "IZ":
            name = self.peek(t, i + 2)
            i += 3
            args = []
            while i < len(t) and self.peek(t, i) != "MKAY":
                i = self.skip(t, i, "AN")
                i = self.skip(t, i, "YR")
                e, i = self.parse_expr(t, i)
                args.append(e)
            i = self.skip(t, i, "MKAY")
            return (lambda env: self.call(name, [a(env) for a in args])), i
        if text == "WIN":
            return (lambda env: True), i + 1
        if text == "FAIL":
            return (lambda env: False), i + 1
        if text == "NOOB":
            return (lambda env: None), i + 1
        if INT_RE.match(text):
            return (lambda env: int(text)), i + 1
        if FLOAT_RE.match(text):
            return (lambda env: float(text)), i + 1
        name = text
        return (lambda env: lookup(env, name)), i + 1

    def peek(self, t, i):
        return t[i][1] if i < len(t) and t[i][0] == "word" else None

    def expect(self, t, i, word):
        if self.peek(t, i) != word:
            raise LolError(f"expected '{word}' near: {' '.join(x[1] for x in t)}")

    def skip(self, t, i, word):
        return i + 1 if self.peek(t, i) == word else i

    # --- statements

    def parse_stmt(self):
        stmt = self.stmts[self.pos]
        self.pos += 1
        w = self.words(stmt)

        if w[0] in ("HAI", "KTHXBYE") or (w[0] == "CAN" and w[1] == "HAS"):
            return lambda env: None
        if w[:3] == ["I", "HAS", "A"]:
            name = w[3]
            if len(w) > 4 and w[4] == "ITZ":
                expr, _ = self.parse_expr(stmt, 5)
            else:
                expr = lambda env: None
            return lambda env: env.__setitem__(name, expr(env))
        if w[0] == "VISIBLE":
            no_newline = False
            if stmt and stmt[-1] == ("word", "!"):
                stmt = stmt[:-1]
                no_newline = True
            elif stmt[-1][0] == "word" and stmt[-1][1].endswith("!"):
                stmt = stmt[:-1] + [("word", stmt[-1][1][:-1])]
                no_newline = True
            parts = []
            i = 1
            while i < len(stmt):
                i = self.skip(stmt, i, "AN")
                e, i = self.parse_expr(stmt, i)
                parts.append(e)

            def visible(env):
                text = "".join(to_str(p(env)) for p in parts)
                sys.stdout.write(text + ("" if no_newline else "\n"))
                sys.stdout.flush()

            return visible
        if w[0] == "GIMMEH":
            name = w[1]

            def gimmeh(env):
                lookup(env, name)  # must be declared
                env[name] = sys.stdin.readline().rstrip("\r\n")

            return gimmeh
        if w[0] == "GTFO":
            def gtfo(env):
                raise LolBreak()
            return gtfo
        if w[:2] == ["FOUND", "YR"]:
            expr, _ = self.parse_expr(stmt, 2)

            def found(env):
                raise LolReturn(expr(env))

            return found
        if w[:2] == ["O", "RLY?"]:
            return self.parse_o_rly()
        if w[0] == "WTF?":
            return self.parse_wtf()
        if w[:2] == ["IM", "IN"]:
            return self.parse_loop(stmt, w)
        if w[:3] == ["HOW", "IZ", "I"]:
            self.parse_function(stmt, w)
            return lambda env: None
        if len(w) > 1 and w[1] == "R":
            name = w[0]
            expr, _ = self.parse_expr(stmt, 2)

            def assign(env):
                lookup(env, name)  # must be declared
                env[name] = expr(env)

            return assign
        if len(w) > 3 and w[1:4] == ["IS", "NOW", "A"]:
            name, type_name = w[0], w[4]
            return lambda env: env.__setitem__(name, cast(lookup(env, name), type_name))
        # bare expression: evaluate into IT
        expr, _ = self.parse_expr(stmt, 0)
        return lambda env: env.__setitem__("IT", expr(env))

    def parse_o_rly(self):
        if self.next_starts_with("YA", "RLY"):
            self.pos += 1
        ya_block = self.parse_block([("MEBBE",), ("NO", "WAI"), ("OIC",)])
        mebbes = []
        while self.next_starts_with("MEBBE"):
            stmt = self.stmts[self.pos]
            self.pos += 1
            cond, _ = self.parse_expr(stmt, 1)
            block = self.parse_block([("MEBBE",), ("NO", "WAI"), ("OIC",)])
            mebbes.append((cond, block))
        no_block = []
        if self.next_starts_with("NO", "WAI"):
            self.pos += 1
            no_block = self.parse_block([("OIC",)])
        self.pos += 1  # OIC

        def o_rly(env):
            if truthy(env.get("IT")):
                run_block(ya_block, env)
                return
            for cond, block in mebbes:
                if truthy(cond(env)):
                    run_block(block, env)
                    return
            run_block(no_block, env)

        return o_rly

    def parse_wtf(self):
        cases = []
        default = None
        while not self.next_starts_with("OIC"):
            stmt = self.stmts[self.pos]
            w = self.words(stmt)
            if w[0] == "OMG":
                self.pos += 1
                literal, _ = self.parse_expr(stmt, 1)
                block = self.parse_block([("OMG",), ("OMGWTF",), ("OIC",)])
                cases.append((literal, block))
            elif w[0] == "OMGWTF":
                self.pos += 1
                default = self.parse_block([("OIC",)])
            else:
                raise LolError(f"unexpected statement in WTF?: {' '.join(w)}")
        self.pos += 1  # OIC

        def wtf(env):
            matched = False
            try:
                for literal, block in cases:
                    if matched or same(env.get("IT"), literal(env)):
                        matched = True
                        run_block(block, env)
                if not matched and default is not None:
                    run_block(default, env)
            except LolBreak:
                pass

        return wtf

    def parse_loop(self, stmt, w):
        op = var = None
        cond = None
        until = False
        i = 4  # past IM IN YR <label>
        if self.peek(stmt, i) in ("UPPIN", "NERFIN"):
            op = self.peek(stmt, i)
            self.expect(stmt, i + 1, "YR")
            var = self.peek(stmt, i + 2)
            i += 3
        if self.peek(stmt, i) in ("TIL", "WILE"):
            until = self.peek(stmt, i) == "TIL"
            cond, i = self.parse_expr(stmt, i + 1)
        body = self.parse_block([("IM", "OUTTA")])
        self.pos += 1  # IM OUTTA YR label

        def loop(env):
            if var is not None and var not in env:
                env[var] = 0
            try:
                while True:
                    if cond is not None:
                        ok = truthy(cond(env))
                        if ok if until else not ok:
                            break
                    run_block(body, env)
                    if var is not None:
                        env[var] += 1 if op == "UPPIN" else -1
            except LolBreak:
                pass

        return loop

    def parse_function(self, stmt, w):
        name = w[3]
        params = []
        i = 4
        while i < len(stmt):
            i = self.skip(stmt, i, "AN")
            i = self.skip(stmt, i, "YR")
            params.append(self.peek(stmt, i))
            i += 1
        body = self.parse_block([("IF", "U", "SAY", "SO")])
        self.pos += 1
        self.funcs[name] = (params, body)

    def call(self, name, args):
        if name not in self.funcs:
            raise LolError(f"unknown function '{name}'")
        params, body = self.funcs[name]
        if len(args) != len(params):
            raise LolError(f"function '{name}' expects {len(params)} arguments")
        env = dict(zip(params, args))
        env["IT"] = None
        try:
            run_block(body, env)
        except LolReturn as ret:
            return ret.value
        except LolBreak:
            pass
        return None

    def run(self):
        program = self.parse_block([])
        env = {"IT": None}
        run_block(program, env)


def run_block(block, env):
    for stmt in block:
        stmt(env)


def lookup(env, name):
    if name == "IT":
        return env.get("IT")
    if name not in env:
        raise LolError(f"variable '{name}' has not been declared")
    return env[name]


def interp_yarn(text, env):
    return re.sub(r"\x00(.*?)\x00", lambda m: to_str(lookup(env, m.group(1))), text)


def math_op(op, a, b):
    a, b = to_num(a), to_num(b)
    if op == "SUM":
        return a + b
    if op == "DIFF":
        return a - b
    if op == "PRODUKT":
        return a * b
    if op == "QUOSHUNT":
        result = a / b
        return int(result) if isinstance(a, int) and isinstance(b, int) else result
    if op == "MOD":
        return a % b
    if op == "BIGGR":
        return max(a, b)
    return min(a, b)


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python lolcode.py <program.lol>")
    with open(sys.argv[1], encoding="utf-8") as f:
        statements = tokenize(f.read())
    try:
        Interpreter(statements).run()
    except LolError as e:
        sys.exit(f"lolcode error: {e}")


if __name__ == "__main__":
    main()
