# esolangs

A collection of small programs written in esoteric programming languages, each
with a way to run it. Most languages have a self-contained interpreter written
in Python; Shakespeare uses a published interpreter, and Piet has its own VS Code
extension.

The project is managed with [uv](https://docs.astral.sh/uv/). All commands below
are run from the repository root.

## Brainfuck

Interpreted by `brainfuck/bf.py`. Pass the path to a `.bf` file:

```
uv run python brainfuck/bf.py brainfuck/<program>.bf
```

Programs read from standard input and write to standard output. If a program
expects input, type it after launching (or pipe it in).

## Chef

Interpreted by `chef/chef.py`. Pass the path to a `.chef` file:

```
uv run python chef/chef.py chef/<program>.chef
```

## COW

Interpreted by `cow/cow.py`. Pass the path to a `.cow` file:

```
uv run python cow/cow.py cow/<program>.cow
```

## LOLCODE

Interpreted by `lolcode/lolcode.py`. Pass the path to a `.lol` file:

```
uv run python lolcode/lolcode.py lolcode/<program>.lol
```

## Whitespace

Interpreted by `whitespace/whitespace.py`. Pass the path to a `.ws` file:

```
uv run python whitespace/whitespace.py whitespace/<program>.ws
```

Only spaces, tabs, and newlines are significant; any other characters in the
file are treated as comments.

## Shakespeare

Shakespeare programs run with the
[`shakespearelang`](https://pypi.org/project/shakespearelang/) interpreter. It is
already listed as a dependency, but if it is missing add it once with:

```
uv add shakespearelang
```

On Windows the interpreter also needs a `readline` implementation, which the
standard library does not provide. Add it once with:

```
uv add pyreadline3
```

Then run a `.spl` file with:

```
uv run shakespeare run shakespeare/<program>.spl
```

## Piet

Piet programs are images (`.piet` / `.png`), so they are created, edited, and run
with the dedicated VS Code extension rather than a command-line interpreter:

**https://github.com/Galacticica/vscode-piet**

Open a `.piet` file with the extension's editor to paint the program, then use
the built-in runner and step debugger to execute it. See that repository for
installation and usage.
