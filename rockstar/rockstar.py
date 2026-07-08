#!/usr/bin/env python3
"""Rockstar language interpreter (a working subset).

Reference: https://codewithrockstar.com/

Implements:
  - Poetic number literals ("X is a big bad wolf" -> 1345)
  - Poetic string literals ("Johnny says hello world")
  - Numeric/string/boolean/null/mysterious literals
  - Variables: common ("my heart"), proper ("Tommy Two-Times"), simple ("gina")
  - Pronouns (it/he/she/him/her/them/they/ze/hir/...)
  - Assignment: `Put ... into X`, `Let X be ...`, `X is <poetic>`
  - Arithmetic: plus/with, minus/without, times/of, over
  - Comparison: is / isn't / greater / less / as X as
  - Logical: and / or / nor / not
  - Control flow: If / Else / While / Until (block ends on blank line)
  - Increment/decrement: `Build X up`, `Knock X down` (with extra `, up`/`, down`)
  - I/O: Say/Shout/Whisper/Scream, Listen to X
  - Functions: `F takes A and B` ... `Give back E`, called as `F taking A, B`
  - `Break` / `Continue` / `Take it to the top` / `Break it down`
  - Line comments in parentheses (...)
"""

import re
import sys

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

COMMON_PREFIXES = {'a', 'an', 'the', 'my', 'your', 'our', 'his', 'her',
                   'their', 'its'}
PRONOUNS = {'it', 'he', 'she', 'him', 'her', 'them', 'they', 'ze', 'hir',
            'zie', 'zir', 'xe', 'xem', 've', 'ver'}
SAY_KEYWORDS = {'say', 'shout', 'whisper', 'scream'}
POETIC_ASSIGN_VERBS = {'is', 'was', 'were', 'are', "'s", "'re"}
BOOLEAN_TRUE = {'true', 'right', 'yes', 'ok'}
BOOLEAN_FALSE = {'false', 'wrong', 'no', 'lies'}
NULL_WORDS = {'null', 'nothing', 'nowhere', 'nobody', 'empty', 'gone'}
MYSTERIOUS_WORDS = {'mysterious'}

# Words that are reserved (won't be treated as variable-body words when the
# statement is looking for a value)
KEYWORDS = (POETIC_ASSIGN_VERBS | BOOLEAN_TRUE | BOOLEAN_FALSE | NULL_WORDS
            | MYSTERIOUS_WORDS | {
                'plus', 'with', 'minus', 'without', 'times', 'of', 'over',
                'and', 'or', 'nor', 'not',
                'if', 'else', 'while', 'until',
                'put', 'let', 'be', 'into', 'in',
                'listen', 'to',
                'say', 'shout', 'whisper', 'scream',
                'build', 'up', 'knock', 'down',
                'give', 'back', 'return', 'send',
                'takes', 'taking', 'wants',
                'break', 'continue', 'take', 'the', 'top', 'it',
                'greater', 'bigger', 'higher', 'stronger',
                'less', 'smaller', 'lower', 'weaker',
                'great', 'big', 'high', 'strong',
                'little', 'small', 'low', 'weak',
                'than', 'as',
            })

# --------------------------------------------------------------------------
# Poetic literal
# --------------------------------------------------------------------------

def poetic_number_from_text(text):
    """Convert a poetic literal (rest-of-line) to a number.

    Split into words on whitespace/punctuation; the letter count of each word
    mod 10 becomes a digit. A '.' introduces the fractional part."""
    # Tokens are runs of letters (with apostrophes ignored) plus '.'
    parts = re.findall(r"[A-Za-z']+|\.", text)
    digits = []
    frac = []
    saw_dot = False
    for p in parts:
        if p == '.':
            if not saw_dot:
                saw_dot = True
            continue
        letters = re.sub(r"[^A-Za-z]", "", p)
        d = str(len(letters) % 10)
        (frac if saw_dot else digits).append(d)
    intp = ''.join(digits) or '0'
    if saw_dot and frac:
        return float(f"{intp}.{''.join(frac)}")
    return int(intp)

# --------------------------------------------------------------------------
# Tokenizer
# --------------------------------------------------------------------------

def strip_comments(source):
    """Remove parenthesized comments."""
    out = []
    depth = 0
    for c in source:
        if c == '(':
            depth += 1
        elif c == ')':
            if depth > 0:
                depth -= 1
        elif depth == 0:
            out.append(c)
    return ''.join(out)


def tokenize(line):
    """Split a line into tokens. String literals stay whole; commas are their
    own tokens; everything else splits on whitespace."""
    tokens = []
    i = 0
    while i < len(line):
        c = line[i]
        if c.isspace():
            i += 1
        elif c == '"':
            j = line.find('"', i + 1)
            if j == -1:
                raise SyntaxError(f"Unterminated string in: {line}")
            tokens.append(line[i:j+1])
            i = j + 1
        elif c == ',':
            tokens.append(',')
            i += 1
        elif c == '&':
            tokens.append('&')
            i += 1
        else:
            j = i
            while j < len(line) and not line[j].isspace() and line[j] not in ',&':
                j += 1
            tokens.append(line[i:j])
            i = j
    return tokens

# --------------------------------------------------------------------------
# Environment
# --------------------------------------------------------------------------

class ReturnSignal(Exception):
    def __init__(self, value):
        self.value = value

class BreakSignal(Exception):
    pass

class ContinueSignal(Exception):
    pass


class Env:
    def __init__(self, parent=None):
        self.parent = parent
        self.vars = {}
        # Last variable *set or referenced by name* — used by pronouns
        self.last_var = None if parent is None else parent.last_var

    def _find_scope(self, name):
        s = self
        while s is not None:
            if name in s.vars:
                return s
            s = s.parent
        return None

    def get(self, name):
        s = self._find_scope(name)
        if s is None:
            return None
        return s.vars[name]

    def set(self, name, value):
        # Assignments always affect the nearest existing binding, or create in
        # the current scope if none exists.
        s = self._find_scope(name)
        if s is None:
            s = self
        s.vars[name] = value
        self._update_pronoun(name)

    def _update_pronoun(self, name):
        e = self
        while e is not None:
            e.last_var = name
            e = e.parent

# --------------------------------------------------------------------------
# Variable & literal token parsing
# --------------------------------------------------------------------------

def looks_capitalized(tok):
    return bool(tok) and tok[0].isupper() and tok.isalpha()


def try_parse_variable(tokens, i, env):
    """Try to consume a variable name starting at tokens[i].
    Returns (canonical_name, new_i) or (None, i)."""
    if i >= len(tokens):
        return None, i
    t = tokens[i]
    tl = t.lower()
    if tl in PRONOUNS:
        if env.last_var is None:
            raise RuntimeError("Pronoun used with no antecedent")
        return env.last_var, i + 1
    # common variable: prefix + one lowercase word
    if tl in COMMON_PREFIXES and i + 1 < len(tokens):
        nxt = tokens[i+1]
        if nxt and nxt[0].isalpha() and nxt.lower() not in KEYWORDS:
            # Require nxt to be a bare word (letters/apostrophes/hyphens)
            if re.match(r"^[A-Za-z][A-Za-z'\-]*$", nxt):
                return (f"{tl} {nxt.lower()}", i + 2)
    # proper variable: one or more Capitalized words
    if looks_capitalized(t) and tl not in KEYWORDS:
        parts = [t]
        j = i + 1
        while j < len(tokens) and looks_capitalized(tokens[j]) and tokens[j].lower() not in KEYWORDS:
            parts.append(tokens[j])
            j += 1
        return (" ".join(p.lower() for p in parts), j)
    # simple variable: one lowercase word that isn't a keyword
    if t and t[0].isalpha() and t[0].islower() and tl not in KEYWORDS:
        if re.match(r"^[A-Za-z][A-Za-z'\-]*$", t):
            return (tl, i + 1)
    return None, i


def try_parse_literal(tokens, i):
    if i >= len(tokens):
        return False, None, i
    t = tokens[i]
    tl = t.lower()
    # string
    if t.startswith('"') and t.endswith('"'):
        return True, t[1:-1], i + 1
    # number
    if re.match(r"^-?\d+(\.\d+)?$", t):
        v = float(t) if '.' in t else int(t)
        return True, v, i + 1
    if tl in BOOLEAN_TRUE:
        return True, True, i + 1
    if tl in BOOLEAN_FALSE:
        return True, False, i + 1
    if tl in NULL_WORDS:
        return True, None, i + 1
    if tl in MYSTERIOUS_WORDS:
        return True, ('__mysterious__',), i + 1
    return False, None, i


# --------------------------------------------------------------------------
# Expression parser (recursive descent)
# --------------------------------------------------------------------------

class ExprParser:
    """Parses a token slice into an AST expression node."""

    def __init__(self, tokens, env):
        self.t = tokens
        self.i = 0
        self.env = env

    def peek(self, n=0):
        if self.i + n < len(self.t):
            return self.t[self.i + n]
        return None

    def peek_lower(self, n=0):
        p = self.peek(n)
        return p.lower() if p else None

    def eat(self):
        v = self.t[self.i]
        self.i += 1
        return v

    def at_end(self):
        return self.i >= len(self.t)

    # Grammar entry
    def parse(self):
        node = self.parse_or()
        return node

    def parse_or(self):
        left = self.parse_and()
        while self.peek_lower() in ('or', 'nor'):
            op = self.eat().lower()
            right = self.parse_and()
            left = ('or', left, right) if op == 'or' else ('nor', left, right)
        return left

    def parse_and(self):
        left = self.parse_not()
        while self.peek_lower() == 'and':
            self.eat()
            right = self.parse_not()
            left = ('and', left, right)
        return left

    def parse_not(self):
        if self.peek_lower() == 'not':
            self.eat()
            return ('not', self.parse_not())
        return self.parse_cmp()

    def parse_cmp(self):
        left = self.parse_add()
        while True:
            p = self.peek_lower()
            if p not in ('is', 'was', 'are', 'were',
                         "isn't", 'isnt', "ain't", 'aint',
                         "aren't", 'arent',
                         "wasn't", 'wasnt', "weren't", 'werent'):
                break
            neg = p not in ('is', 'was', 'are', 'were')
            self.eat()
            op = None
            nxt = self.peek_lower()
            if nxt in ('greater', 'bigger', 'higher', 'stronger'):
                self.eat()
                if self.peek_lower() == 'than':
                    self.eat()
                op = 'gt'
            elif nxt in ('less', 'smaller', 'lower', 'weaker'):
                self.eat()
                if self.peek_lower() == 'than':
                    self.eat()
                op = 'lt'
            elif nxt == 'as':
                self.eat()
                adj = self.peek_lower()
                self.eat()
                if self.peek_lower() == 'as':
                    self.eat()
                if adj in ('great', 'big', 'high', 'strong'):
                    op = 'gte'
                elif adj in ('little', 'small', 'low', 'weak'):
                    op = 'lte'
                else:
                    raise SyntaxError(f"Unknown comparison adjective: {adj}")
            else:
                op = 'eq'
            right = self.parse_add()
            if neg and op == 'eq':
                left = ('neq', left, right)
            elif neg and op == 'gt':
                left = ('lte', left, right)
            elif neg and op == 'lt':
                left = ('gte', left, right)
            elif neg and op == 'gte':
                left = ('lt', left, right)
            elif neg and op == 'lte':
                left = ('gt', left, right)
            else:
                left = (op, left, right)
        return left

    def parse_add(self):
        left = self.parse_mul()
        while self.peek_lower() in ('plus', 'with', 'minus', 'without'):
            op = self.eat().lower()
            right = self.parse_mul()
            if op in ('plus', 'with'):
                left = ('add', left, right)
            else:
                left = ('sub', left, right)
        return left

    def parse_mul(self):
        left = self.parse_atom()
        while self.peek_lower() in ('times', 'of', 'over'):
            op = self.eat().lower()
            right = self.parse_atom()
            if op in ('times', 'of'):
                left = ('mul', left, right)
            else:
                left = ('div', left, right)
        return left

    def parse_atom(self):
        # literal?
        ok, val, ni = try_parse_literal(self.t, self.i)
        if ok:
            self.i = ni
            return ('lit', val)
        # function call: NAME taking ARG, ARG, ARG
        # Try to parse variable, then look for 'taking'
        var, ni = try_parse_variable(self.t, self.i, self.env)
        if var is not None:
            # peek for 'taking'
            if ni < len(self.t) and self.t[ni].lower() == 'taking':
                fname = var
                self.i = ni + 1
                args = [self.parse_or()]
                while self.peek() == ',' or self.peek_lower() == 'and' or self.peek() == '&':
                    self.eat()
                    args.append(self.parse_or())
                return ('call', fname, args)
            self.i = ni
            return ('var', var)
        # unknown
        raise SyntaxError(f"Cannot parse expression at token {self.i}: "
                          f"{self.t[self.i] if self.i < len(self.t) else '<eof>'} "
                          f"in {self.t}")


# --------------------------------------------------------------------------
# Statement parser
# --------------------------------------------------------------------------

def parse_statement(line, env_for_names):
    """Turn a single non-blank line into a statement dict.

    env_for_names is passed only so pronoun-style variable references know the
    current last_var. It is not mutated during parsing."""
    tokens = tokenize(line)
    if not tokens:
        return None
    lower0 = tokens[0].lower()

    # ---- Simple leading keywords ----
    if lower0 in SAY_KEYWORDS:
        expr_tokens = tokens[1:]
        parser = ExprParser(expr_tokens, env_for_names)
        expr = parser.parse()
        return {'type': 'say', 'expr': expr}

    if lower0 == 'listen':
        # "Listen to <var>"
        idx = 1
        if idx < len(tokens) and tokens[idx].lower() == 'to':
            idx += 1
        var, ni = try_parse_variable(tokens, idx, env_for_names)
        if var is None:
            raise SyntaxError(f"Expected variable after 'Listen to': {line}")
        return {'type': 'listen', 'var': var}

    if lower0 == 'put':
        # "Put <expr> into <var>"
        # Find 'into' index (rightmost 'into' to be safe)
        into_idx = None
        for k in range(len(tokens) - 1, 0, -1):
            if tokens[k].lower() == 'into':
                into_idx = k
                break
        if into_idx is None:
            raise SyntaxError(f"Missing 'into' in: {line}")
        expr_tokens = tokens[1:into_idx]
        var, ni = try_parse_variable(tokens, into_idx + 1, env_for_names)
        if var is None:
            raise SyntaxError(f"Expected variable after 'into': {line}")
        parser = ExprParser(expr_tokens, env_for_names)
        expr = parser.parse()
        return {'type': 'assign', 'var': var, 'expr': expr}

    if lower0 == 'let':
        # "Let <var> be <expr>" (also augmented: be plus/minus/times/over <e>)
        var, ni = try_parse_variable(tokens, 1, env_for_names)
        if var is None:
            raise SyntaxError(f"Expected variable after 'Let': {line}")
        if ni >= len(tokens) or tokens[ni].lower() != 'be':
            raise SyntaxError(f"Expected 'be' after variable in Let: {line}")
        ni += 1
        aug_op = None
        if ni < len(tokens):
            w = tokens[ni].lower()
            if w in ('plus', 'with'):
                aug_op = 'add'; ni += 1
            elif w in ('minus', 'without'):
                aug_op = 'sub'; ni += 1
            elif w in ('times', 'of'):
                aug_op = 'mul'; ni += 1
            elif w == 'over':
                aug_op = 'div'; ni += 1
        parser = ExprParser(tokens[ni:], env_for_names)
        rhs = parser.parse()
        if aug_op is not None:
            rhs = (aug_op, ('var', var), rhs)
        return {'type': 'assign', 'var': var, 'expr': rhs}

    if lower0 == 'build':
        var, ni = try_parse_variable(tokens, 1, env_for_names)
        if var is None:
            raise SyntaxError(f"Expected variable after Build: {line}")
        # count of "up" tokens (comma-separated in the source)
        count = 0
        for tok in tokens[ni:]:
            if tok.lower() == 'up':
                count += 1
        if count == 0:
            count = 1
        return {'type': 'incdec', 'var': var, 'delta': count}

    if lower0 == 'knock':
        var, ni = try_parse_variable(tokens, 1, env_for_names)
        if var is None:
            raise SyntaxError(f"Expected variable after Knock: {line}")
        count = 0
        for tok in tokens[ni:]:
            if tok.lower() == 'down':
                count += 1
        if count == 0:
            count = 1
        return {'type': 'incdec', 'var': var, 'delta': -count}

    if lower0 == 'if':
        parser = ExprParser(tokens[1:], env_for_names)
        cond = parser.parse()
        return {'type': 'if', 'cond': cond, 'body': [], 'else': None}

    if lower0 == 'else':
        return {'type': 'else'}

    if lower0 == 'while':
        parser = ExprParser(tokens[1:], env_for_names)
        cond = parser.parse()
        return {'type': 'while', 'cond': cond, 'body': []}

    if lower0 == 'until':
        parser = ExprParser(tokens[1:], env_for_names)
        cond = parser.parse()
        return {'type': 'until', 'cond': cond, 'body': []}

    if lower0 in ('give', 'return', 'send'):
        # "Give back <expr>" / "Return <expr>" / "Send <expr>" — also plain "Give back"
        idx = 1
        if idx < len(tokens) and tokens[idx].lower() == 'back':
            idx += 1
        if idx >= len(tokens):
            return {'type': 'return', 'expr': ('lit', None)}
        parser = ExprParser(tokens[idx:], env_for_names)
        return {'type': 'return', 'expr': parser.parse()}

    if lower0 == 'break':
        return {'type': 'break'}
    if lower0 == 'continue':
        return {'type': 'continue'}
    if lower0 == 'take' and len(tokens) >= 5 \
            and [t.lower() for t in tokens[1:5]] == ['it', 'to', 'the', 'top']:
        return {'type': 'continue'}

    # ---- Otherwise: could be a `<var> is <poetic>` assignment OR a
    #      `<var> takes ...` function definition, OR just an expression stmt.
    var, ni = try_parse_variable(tokens, 0, env_for_names)
    if var is not None and ni < len(tokens):
        nxt = tokens[ni].lower()
        # Function definition: "F takes A and B and C"
        if nxt == 'takes' or nxt == 'wants':
            params = []
            j = ni + 1
            while j < len(tokens):
                p, nj = try_parse_variable(tokens, j, env_for_names)
                if p is None:
                    break
                params.append(p)
                j = nj
                # skip 'and', ',', '&'
                while j < len(tokens) and (tokens[j] == ',' or tokens[j] == '&' or tokens[j].lower() == 'and'):
                    j += 1
            return {'type': 'func', 'name': var, 'params': params, 'body': []}
        # Poetic assignment: "X is Y..."
        if nxt in POETIC_ASSIGN_VERBS:
            # If the RHS is a single literal we take it as-is; otherwise poetic.
            rest_tokens = tokens[ni+1:]
            # Check for literal first
            if len(rest_tokens) == 1:
                ok, val, _ = try_parse_literal(rest_tokens, 0)
                if ok:
                    return {'type': 'assign', 'var': var,
                            'expr': ('lit', val)}
            # says-poetic-string: "X says hello world"
            if nxt == 'says':
                rest_text = line.split(None, )  # unused
                # rebuild from original line to preserve spacing
                m = re.match(r'^\s*\S+(?:\s+\S+)*?\s+says\s+(.*)$', line)
                if m:
                    return {'type': 'assign', 'var': var,
                            'expr': ('lit', m.group(1))}
            # Otherwise: poetic number
            rest_text = ' '.join(rest_tokens)
            val = poetic_number_from_text(rest_text)
            return {'type': 'assign', 'var': var, 'expr': ('lit', val)}
        # "X says ..." poetic string
        if nxt == 'says':
            m = re.match(r'^\s*\S+(?:\s+\S+)*?\s+says\s+(.*)$', line)
            if m:
                return {'type': 'assign', 'var': var,
                        'expr': ('lit', m.group(1))}

    # Fall back: parse as an expression statement (function call side-effect)
    parser = ExprParser(tokens, env_for_names)
    expr = parser.parse()
    return {'type': 'expr', 'expr': expr}


# --------------------------------------------------------------------------
# Block parser
# --------------------------------------------------------------------------

def parse_program(source, env):
    src = strip_comments(source)
    lines = src.split('\n')
    # At the top level, blank lines are just whitespace — keep going.
    stmts = []
    i = 0
    while i < len(lines):
        if not lines[i].strip():
            i += 1
            continue
        block, i = parse_block(lines, i, env, allow_else=False)
        stmts.extend(block)
    return stmts


def parse_block(lines, i, env, allow_else):
    """Parse statements until a blank line at the current level.

    Returns (statements, next_index). When allow_else is True and an 'Else'
    line is encountered at this level, parsing stops and returns as if a blank
    line had been seen — the caller handles the else branch."""
    body = []
    while i < len(lines):
        raw = lines[i]
        line = raw.strip()
        if not line:
            return body, i + 1
        first = line.split()[0].lower()
        if allow_else and first == 'else':
            return body, i  # leave else line for caller
        stmt = parse_statement(line, env)
        i += 1
        if stmt is None:
            continue
        if stmt['type'] == 'if':
            sub, i = parse_block(lines, i, env, allow_else=True)
            stmt['body'] = sub
            # Check for else
            if i < len(lines) and lines[i].strip().lower().startswith('else'):
                i += 1
                else_body, i = parse_block(lines, i, env, allow_else=False)
                stmt['else'] = else_body
        elif stmt['type'] in ('while', 'until', 'func'):
            sub, i = parse_block(lines, i, env, allow_else=False)
            stmt['body'] = sub
        body.append(stmt)
    return body, i


# --------------------------------------------------------------------------
# Evaluator
# --------------------------------------------------------------------------

def _truthy(v):
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        return len(v) > 0
    return True


def _coerce_numeric(a, b):
    """Best-effort coercion so int + int stays int."""
    if isinstance(a, bool):
        a = 1 if a else 0
    if isinstance(b, bool):
        b = 1 if b else 0
    return a, b


def evaluate(node, env):
    tag = node[0]
    if tag == 'lit':
        return node[1]
    if tag == 'var':
        return env.get(node[1])
    if tag == 'call':
        _, name, args = node
        func = env.get(name)
        if not isinstance(func, dict) or func.get('__kind__') != 'function':
            raise RuntimeError(f"'{name}' is not a function")
        vals = [evaluate(a, env) for a in args]
        return call_function(func, vals)

    if tag in ('add', 'sub', 'mul', 'div'):
        a = evaluate(node[1], env)
        b = evaluate(node[2], env)
        if tag == 'add':
            if isinstance(a, str) or isinstance(b, str):
                return _to_str(a) + _to_str(b)
            a, b = _coerce_numeric(a, b)
            return a + b
        a, b = _coerce_numeric(a, b)
        if tag == 'sub':
            return a - b
        if tag == 'mul':
            if isinstance(a, str) and isinstance(b, int):
                return a * b
            return a * b
        if tag == 'div':
            if isinstance(a, int) and isinstance(b, int) and b != 0 and a % b == 0:
                return a // b
            return a / b

    if tag in ('eq', 'neq', 'gt', 'lt', 'gte', 'lte'):
        a = evaluate(node[1], env)
        b = evaluate(node[2], env)
        if tag == 'eq':
            return _equal(a, b)
        if tag == 'neq':
            return not _equal(a, b)
        a2, b2 = _coerce_numeric(a, b)
        if tag == 'gt':
            return a2 > b2
        if tag == 'lt':
            return a2 < b2
        if tag == 'gte':
            return a2 >= b2
        if tag == 'lte':
            return a2 <= b2

    if tag == 'and':
        return _truthy(evaluate(node[1], env)) and _truthy(evaluate(node[2], env))
    if tag == 'or':
        return _truthy(evaluate(node[1], env)) or _truthy(evaluate(node[2], env))
    if tag == 'nor':
        return not (_truthy(evaluate(node[1], env)) or _truthy(evaluate(node[2], env)))
    if tag == 'not':
        return not _truthy(evaluate(node[1], env))

    raise RuntimeError(f"Unknown node: {node}")


def _equal(a, b):
    if isinstance(a, bool) or isinstance(b, bool):
        return bool(a) == bool(b)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    return a == b


def _to_str(v):
    if v is None:
        return 'null'
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, float):
        if v.is_integer():
            return str(int(v))
        return str(v)
    return str(v)


def call_function(func, arg_values):
    parent_env = func['__env__']
    params = func['__params__']
    body = func['__body__']
    if len(params) != len(arg_values):
        raise RuntimeError(f"Function expected {len(params)} arg(s), got {len(arg_values)}")
    call_env = Env(parent=parent_env)
    for p, v in zip(params, arg_values):
        call_env.vars[p] = v
    call_env.last_var = params[-1] if params else parent_env.last_var
    try:
        execute_block(body, call_env)
    except ReturnSignal as r:
        return r.value
    return None


def execute_block(stmts, env):
    for stmt in stmts:
        execute(stmt, env)


def execute(stmt, env):
    t = stmt['type']
    if t == 'say':
        print(_to_str(evaluate(stmt['expr'], env)))
    elif t == 'listen':
        try:
            line = input()
        except EOFError:
            line = ''
        # Try to parse as number
        line = line.strip()
        if re.match(r'^-?\d+$', line):
            env.set(stmt['var'], int(line))
        elif re.match(r'^-?\d+\.\d+$', line):
            env.set(stmt['var'], float(line))
        else:
            env.set(stmt['var'], line)
    elif t == 'assign':
        env.set(stmt['var'], evaluate(stmt['expr'], env))
    elif t == 'incdec':
        cur = env.get(stmt['var'])
        if cur is None:
            cur = 0
        if isinstance(cur, bool):
            # Bool toggles regardless of magnitude
            for _ in range(abs(stmt['delta'])):
                cur = not cur
            env.set(stmt['var'], cur)
        else:
            env.set(stmt['var'], cur + stmt['delta'])
    elif t == 'if':
        if _truthy(evaluate(stmt['cond'], env)):
            execute_block(stmt['body'], env)
        elif stmt.get('else'):
            execute_block(stmt['else'], env)
    elif t == 'while':
        while _truthy(evaluate(stmt['cond'], env)):
            try:
                execute_block(stmt['body'], env)
            except BreakSignal:
                break
            except ContinueSignal:
                continue
    elif t == 'until':
        while not _truthy(evaluate(stmt['cond'], env)):
            try:
                execute_block(stmt['body'], env)
            except BreakSignal:
                break
            except ContinueSignal:
                continue
    elif t == 'break':
        raise BreakSignal()
    elif t == 'continue':
        raise ContinueSignal()
    elif t == 'return':
        raise ReturnSignal(evaluate(stmt['expr'], env))
    elif t == 'func':
        func = {
            '__kind__': 'function',
            '__params__': stmt['params'],
            '__body__': stmt['body'],
            '__env__': env,
        }
        env.set(stmt['name'], func)
    elif t == 'expr':
        evaluate(stmt['expr'], env)
    else:
        raise RuntimeError(f"Unknown statement: {stmt}")


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def run(source):
    env = Env()
    stmts = parse_program(source, env)
    execute_block(stmts, env)


def main(argv):
    if len(argv) < 2:
        print("Usage: python rockstar.py <program.rock>", file=sys.stderr)
        sys.exit(2)
    with open(argv[1], 'r', encoding='utf-8') as f:
        src = f.read()
    run(src)


if __name__ == '__main__':
    main(sys.argv)
