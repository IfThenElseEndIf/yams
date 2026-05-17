#!/usr/bin/env python3

def parse(code):
      result = []

      for i, line in enumerate(code.splitlines()):
            if not line: continue
            if line.startswith("#!") and i == 0: continue
            for word in line.split():
                  result.append(word)

      return tuple(result)

def number(s, /):
      if isinstance(s, (int, float)): return True
      try:
            n = float(s)
            return int(n) if n.is_integer() else n
      except ValueError:
            return

def error(m, /):
      from sys import stderr
      print(f"[yams] error: {m}", file=stderr)

def importfile(path):
      path = path.strip()
      if len(path.split(".")) == 1:
            path += ".yams"

      try:
            with open(path.strip()) as file:
                  contents = file.read()
      except Exception:
            raise NameError(f"couldn't find or get imported file (\"{path}\")")

      if not (p := parencheck(contents))[0]:
            raise ValueError(f"did not terminate {p[1]} object")

      return parse(contents)

def typeof(v, /):
      if isinstance(v, (int, float)):
            return "number"
      elif isinstance(v, str):
            return "word"
      elif isinstance(v, tuple):
            return "words"
      elif isinstance(v, list):
            return "list"
      elif isinstance(v, Function):
            return "function"
      elif v is None:
            return "null"

def isnumber(*v):
      return all(isinstance(e, (int, float)) for e in v)

def ischar(c, /):
      if not isinstance(c, int):
            return False
      if c not in range(256):
            return False
      return True

def isstr(s, /):
      if not isinstance(s, list): return False
      return all(ischar(c) for c in s)

class Exit(Exception):
      pass

def parencheck(s, /):
      if not isinstance(s, str):
            s = "\n".join(s)
      parencount = 0
      onstring = False
      bracketcount = 0
      oncomment = False

      for word in parse(s):
            if oncomment:
                  if word == "*/":
                        oncomment = not oncomment
                  continue
            if onstring:
                  if word == "\"":
                        onstring = not onstring
                  continue

            if word == "(":
                  parencount += 1
            elif word == ")":
                  parencount -= 1
            elif word == "\"":
                  onstring = not onstring
            elif word == "[":
                  bracketcount += 1
            elif word == "]":
                  bracketcount -= 1
            elif word == "/*":
                  oncomment = not oncomment
            else:
                  continue

      if onstring or parencount or bracketcount or oncomment:
            return False, "string" if onstring else "words" if parencount else "list" if bracketcount else "comment"

      return True, None

class Function:
      def __init__(self, args, code):
            if len(args) != len(set(args)):
                  raise TypeError("repeated argument definitions in function")

            if not (p := parencheck(code))[0]:
                  raise ValueError(f"did not terminate {p[1]} object in function")

            self.args, self.code = args, code

      def __len__(self):
            return len(self.args)

      def __call__(self, *args):
            if len(args) != len(self):
                  raise TypeError("function was given more or less arguments than needed")

            argdict = {self.args[i]:arg for i, arg in enumerate(args)}

            result = []

            parens = 0
            onstr = False
            oncomment = False

            for word in self.code:
                  if oncomment:
                        if word == "*/":
                              oncomment = not oncomment
                        result.append(word)
                        continue

                  if onstr:
                        if word == "\"":
                              onstr = not onstr
                        result.append(word)
                        continue

                  if word == "\"":
                        onstr = not onstr
                        result.append(word)
                        continue
                  elif word == "/*":
                        oncomment = True
                        result.append(word)
                        continue
                  elif word == "(":
                        parens += 1
                        result.append(word)
                        continue
                  elif word == ")":
                        parens -= 1
                        result.append(word)
                        continue

                  if (word in argdict) and (parens == 0) and (not onstr):
                        result.append((argdict[word],))
                  else:
                        result.append(word)

            return result

def tostr(x, /):
      if typeof(x) == "number":
            return [ord(c) for c in str(x)]
      elif typeof(x) == "null":
            return [ord(c) for c in "null"]
      elif typeof(x) == "words":
            return [ord(c) for c in (f"( {' '.join(word for word in x)} )" if x else "()")]
      elif typeof(x) == "word":
            return [ord(c) for c in f"'{x}"]
      else:
            raise TypeError(f"cannot convert {typeof(x)} object to string object")

def run(code, *argv, mute=False, stack=None, variables=None, macros=None, raiseonexit=False):
      stack = [[]] if stack is None else [stack]
      variables = {} if variables is None else variables
      macros = {} if macros is None else macros
      aliases = {}
      argv = [[ord(c) for c in str(a)] for a in argv]

      err = (lambda m: None) if mute else error

      if not (p := parencheck(code))[0]:
            err(f"did not terminate {p[1]} object"); return 1

      def boolean(v, d, m, /):
            if isinstance(v, str):
                  return 1 if (v in d) or (v in m) else 0
            return 1 if v else 0

      SPECIAL = {
            "true", "false", "null", "argv", "read", "readln", "self", # 0
            "do", ",", "'", "print", "println", "length", "exit", "goto", "delete", "boolean", "type", "isstr", "import", "wait", "tostr", # 1
            "+", "-", "*", "/", "**", "<", "=<", ">", ">=", "=", "!=", "is", "define", "cond", "get", "error", "alias", "join", "function", # 2
            "if", "set", # 3
            "(", ")", "[", "]", "\"", "()", "[]", "\"\"", "/*", "/*", "/**/"
      }
      MAXDEPTH = 16

      def isvalidargdef(argdef, /):
            for arg in argdef:
                  if (arg in SPECIAL) or ("'" in arg):
                        return False
            return True

      import time
      try: from readchar import readchar
      except ModuleNotFoundError: readchar = input

      def depth():
            nonlocal stack
            if len(stack) == 1: return None
            if len(stack) == 2 and isinstance(stack[-1], tuple): return None
            else:
                  if isinstance(stack[-1], tuple): return len(stack) - 2
                  return len(stack) - 1

      parencount = 0
      string = False
      parsed = parse(code)
      program_buffer = list(parsed)
      string_buffer = ""
      oncomment = False

      if len(program_buffer) >= 0xFFFFFFFF:
            err(f"program is extremely big"); return 1

      while program_buffer:
            if len(program_buffer) >= 0xFFFFFFFF:
                  err(f"program has expanded way too much"); return 1
            if (depth() is not None) and (depth() not in range(MAXDEPTH)):
                  err(f"extremely deep {typeof(stack[1])} object"); return 1

            instruction = program_buffer[0]
            if isinstance(instruction, tuple):
                  stack[-1].append(instruction[0])
            else:
                  word = instruction

                  if oncomment:
                        if word == "*/":
                              oncomment = not oncomment
                        program_buffer = program_buffer[1:]
                        continue

                  while word in aliases:
                        word = aliases[word]

                  if string:
                        if word == "\"":
                              string = not string
                              stack[-1].append([ord(c) for c in string_buffer])
                              string_buffer = ""
                        else:
                              string_buffer = " ".join(string_buffer.split() + [word])
                        program_buffer = program_buffer[1:]
                        continue

                  if parencount:
                        if word == "(":
                              parencount += 1
                        elif word == ")":
                              parencount -= 1
                              if not parencount:
                                    code_object = stack.pop()
                                    stack[-1].append(code_object)
                                    program_buffer = program_buffer[1:]
                                    continue
                        stack[-1] = stack[-1] + (word,)
                        program_buffer = program_buffer[1:]
                        continue

                  if word == "/*":
                        oncomment = True
                        program_buffer = program_buffer[1:]
                        continue
                  elif word == "/**/":
                        program_buffer = program_buffer[1:]
                        continue
                  elif word.startswith("'"):
                        stack[-1].append(word[1:])
                  elif (word != "'") and ("'" in word):
                        err(f"invalid word '{word}"); return 1
                  elif word in macros:
                        program_buffer[0:1] = macros[word]
                        continue
                  elif (n := number(word)) is not None:
                        stack[-1].append(n)
                  elif word == "null":
                        stack[-1].append(None)
                  elif word == "true":
                        stack[-1].append(1)
                  elif word == "false":
                        stack[-1].append(0)
                  elif word == "argv":
                        stack[-1].append(argv[:])
                  elif word == "read":
                        try:
                              v = readchar()
                              if not v: v = None
                              else: v = ord(v[0])
                        except: v = None
                        stack[-1].append(v)
                  elif word == "readln":
                        try: v = [ord(c) for c in input()]
                        except: v = None
                        stack[-1].append(v)
                  elif word == "self":
                        stack[-1].append(parsed)
                  elif word in {"do", ",", "'", "print", "println", "length", "exit", "goto", "delete", "boolean", "type", "isstr", "import", "wait", "tostr"}:
                        if not stack[-1]:
                              err(f"'{word} expected 1 object but got 0"); return 1
                        x = stack[-1].pop()
                        if word == "do":
                              if typeof(x) not in {"words", "function"}:
                                    err(f"'{word} expected 1 words or function object but got a {typeof(x)} object"); return 1
                              if typeof(x) == "words":
                                    program_buffer[0:1] = x
                                    continue
                              else:
                                    if len(stack[-1]) < len(x):
                                          err(f"not enough arguments for function call (expected {len(x)})"); return 1
                                    program_buffer[0:1] = x(*[stack[-1].pop() for _ in range(len(x))])
                                    continue
                        if word == ",":
                              if not isinstance(x, str):
                                    err(f"'{word} expected 1 word object but got a {typeof(x)} object"); return 1
                              if x in {"(", ")", "[", "]", "\"", "/*", "*/"}:
                                    err(f"cannot call individual parenthesis, bracket, double quote or comment delimiter with ,"); return 1
                              program_buffer[0] = x
                              continue
                        elif word == "'":
                              if not isinstance(x, str):
                                    err(f"'{word} expected 1 word object but got a {typeof(x)} object"); return 1
                              stack[-1].append(f"'{x}")
                        elif word == "print":
                              if not isstr(x):
                                    err(f"'{word} expected a string object (list of integers valid as characters) but got a {typeof(x) if typeof(x) != 'list' else 'non-string list'} object"); return 1
                              for char in x:
                                    print(chr(char), end="")
                        elif word == "println":
                              if not isstr(x):
                                    err(f"'{word} expected a string object (list of integers valid as characters) but got a {typeof(x) if typeof(x) != 'list' else 'non-string list'} object"); return 1
                              for char in x:
                                    print(chr(char), end="")
                              print()
                        elif word == "length":
                              if typeof(x) not in {"list", "words", "word"}:
                                    err(f"cannot get length of {typeof(x)} object"); return 1
                              stack[-1].append(len(x))
                        elif word == "exit":
                              if typeof(x) != "number":
                                    err(f"cannot exit with {typeof(x)} object"); return 1
                              if not isinstance(x, int):
                                    err("cannot exit with non-integer number object"); return 1
                              if raiseonexit:
                                    raise Exit(x)
                              return x
                        elif word == "goto":
                              if typeof(x) != "words":
                                    err(f"'{word} expected 1 words object but got a {typeof(x)} object"); return 1
                              program_buffer = list(parsed)
                              continue
                        elif word == "delete":
                              if typeof(x) != "word":
                                    err(f"'{word} expected 1 word object but got a {typeof(x)} object"); return 1
                              if x in macros:
                                    del macros[x]
                              if x in variables:
                                    del variables[x]
                        elif word == "boolean":
                              stack[-1].append(boolean(x, variables, macros))
                        elif word == "type":
                              stack[-1].append(list(ord(c) for c in typeof(x)))
                        elif word == "isstr":
                              stack[-1].append(boolean(isstr(x), variables, macros))
                        elif word == "import":
                              if not isstr(x):
                                    err(f"'{word} expected a string object (list of integers valid as characters) but got a {typeof(x) if typeof(x) != 'list' else 'non-string list'} object"); return 1
                              try:
                                    module = importfile("".join(chr(c) for c in x))
                              except Exception as e:
                                    err(str(e)); return 1
                              stack[-1].append(module)
                        elif word == "wait":
                              if typeof(x) != "number":
                                    err(f"'{word} expected a number object but got a {typeof(x)} object"); return 1
                              if x < 0:
                                    err(f"'cannot call '{word} with a negative amount of time"); return 1
                              time.sleep(x)
                        elif word == "tostr":
                              try:
                                    stack[-1].append(tostr(x))
                              except TypeError as e:
                                    err(e); return 1
                  elif word in {"+", "-", "*", "/", "**", ">", ">=", "<", "=<", "=", "!=", "is", "define", "cond", "get", "macro", "error", "alias", "join", "function"}:
                        if len(stack[-1]) in {0, 1}:
                              err(f"'{word} expected 2 objects but got {len(stack[-1])} objects"); return 1
                        b, a = stack[-1].pop(), stack[-1].pop()
                        if (word in {"+", "-", "*", "/", "**", ">", ">=", "<", "=<"}) and (not isnumber(a,b)):
                              if typeof(a) != typeof(b):
                                    err(f"'{word} expects 2 number objects but got {typeof(a)} and {typeof(b)} objects")
                              else:
                                    err(f"'{word} expects 2 number objects but got 2 {typeof(a)} objects")
                              return 1
                        if word == "+":
                              stack[-1].append(a + b)
                        elif word == "-":
                              stack[-1].append(a - b)
                        elif word == "*":
                              stack[-1].append(a * b)
                        elif word == "/":
                              try: stack[-1].append(a / b)
                              except DivisionByZero:
                                    err("division by zero"); return 1
                        elif word == "**":
                              stack[-1].append(a ** b)
                        elif word == ">":
                              stack[-1].append(a > b)
                        elif word == ">=":
                              sack[-1].append(a > b)
                        elif word == "<":
                              stack[-1].append(a < b)
                        elif word == "=<":
                              stack[-1].append(a <= b)
                        elif word == "=":
                              stack[-1].append(a == b)
                        elif word == "!=":
                              stack[-1].append(a != b)
                        elif word == "is":
                              stack[-1].append(a is b)
                        elif word == "define":
                              if not isinstance(a, str):
                                    err(f"'{word} expected a word object for its first argument but got a {typeof(a)} object"); return 1
                              if (a in SPECIAL) or (number(a) is not None) or ("'" in a):
                                    err(f"cannot use '{a} as identifier in definition"); return 1
                              if a in macros: del macros[a]
                              variables[a] = b
                        elif word == "cond":
                              if typeof(b) != "words":
                                    err(f"'{word} expected a words object but got a {typeof(b)} object"); return 1
                              if boolean(a, variables, macros):
                                    program_buffer[0:1] = b
                                    continue
                        elif word == "get":
                              if typeof(a) != "list":
                                    err(f"cannot index {typeof(a)} object"); return 1
                              if typeof(b) != "number":
                                    err(f"cannot index list object with {typeof(b)} object"); return 1
                              if not isinstance(b, int):
                                    err(f"cannot index list object with non-integer number object"); return 1
                              stack[-1].append(a[b])
                        elif word == "macro":
                              if not isinstance(a, str):
                                    err(f"'{word} expected a word object for its first argument but got a {typeof(a)} object"); return 1
                              if (a in SPECIAL) or (number(a) is not None) or ("'" in a):
                                    err(f"cannot use '{a} as identifier in macro definition"); return 1
                              if typeof(b) != "words":
                                    err(f"'{word} expected a words object for macro"); return 1
                              if a in variables: del variables[a]
                              macros[a] = b
                        elif word == "error":
                              if not isstr(a):
                                    err(f"'{word} expected a string object (list of integers valid as characters) for its first argument but got a {typeof(x) if typeof(x) != 'list' else 'non-string list'} object"); return 1
                              if typeof(b) != "number":
                                    err(f"cannot exit with {typeof(x)} object"); return 1
                              if not isinstance(b, int):
                                    err("cannot exit with non-integer number object"); return 1
                              err("".join(chr(c) for c in a)); return b
                        elif word == "alias":
                              if typeof(a) != "word":
                                    err(f"'{word} expected a word object for its first argument but got a {typeof(a)} object"); return 1
                              if ("'" in a) and (a != "'"):
                                    err("cannot turn a quotation into an alias"); return 1
                              if typeof(b) != "word":
                                    err(f"'{word} expected a word object for its second argument but got a {typeof(a)} object"); return 1
                              aliases[a] = b
                        elif word == "join":
                              if typeof(a) not in {"list", "words"}:
                                    err(f"'{word} expected a words or list object for its first argument but got a {typeof(a)} object"); return 1
                              if typeof(b) not in {"list", "words"}:
                                    err(f"'{word} expected a words or list object for its second argument but got a {typeof(b)} object"); return 1
                              if typeof(a) != typeof(b):
                                    err(f"cannot join {typeof(a)} object with {typeof(b)} object"); return 1
                              stack[-1].append(a + b)
                        elif word == "function":
                              if typeof(a) != "words":
                                    err(f"'{word} expected a words object for its first argument but got a {typeof(a)} object"); return 1
                              if typeof(b) != "words":
                                    err(f"'{word} expected a words object for its second argument but got a {typeof(b)} object"); return 1
                              if not isvalidargdef(a):
                                    err("bad argument(s) definition in function definition")
                              try: stack[-1].append(Function(a, b))
                              except Exception as exception:
                                    err(f"{exception}"); return 1
                  elif word in {"if", "set"}:
                        if len(stack[-1]) in {0, 1, 2}:
                              err(f"'{word} expected 3 objects but got {len(stack[-1])} object(s)"); return 1
                        c, b, a = stack[-1].pop(), stack[-1].pop(), stack[-1].pop()
                        if word == "if":
                              if boolean(a, variables, macros): stack[-1].append(b)
                              else: stack[-1].append(c)
                        elif word == "set":
                              if typeof(a) != "list":
                                    err(f"cannot index {typeof(a)} object"); return 1
                              if typeof(b) != "number":
                                    err(f"cannot index list object with {typeof(b)} object"); return 1
                              if not isinstance(b, int):
                                    err(f"cannot index list object with non-integer number object"); return 1
                              try: a[b] = c
                              except:
                                    err("list index out of range"); return 1
                  elif word == "(":
                        stack.append(())
                        parencount += 1
                  elif word == ")":
                        err("invalid use for '{word}"); return 1
                  elif word in variables:
                        stack[-1].append(variables[word])
                  elif word == "[":
                        stack.append([])
                  elif word == "]":
                        if len(stack) == 1:
                              err("invalid use for '{word}"); return 1
                        l = stack.pop()
                        stack[-1].append(l)
                  elif word == "()":
                        stack[-1].append(tuple())
                  elif word == "[]":
                        stack[-1].append(list())
                  elif word == "\"":
                        string = not string
                        string_buffer = ""
                  elif word == "\"\"":
                        stack[-1].append(list())
                  else:
                        err(f"unknown word '{word}"); return 1

            program_buffer = program_buffer[1:]

      if string:
            err("did not terminate string object"); return 1
      elif parencount != 0:
            err("did not terminate words object"); return 1
      elif len(stack) != 1:
            err("did not terminate list object"); return 1
      elif oncomment:
            err("did not terminate comment"); return 1

      return 0

def repl():
      stack, variables, macros = [], {}, {}

      while True:
            try:
                  c = input("yams % ")
            except (OSError, KeyboardInterrupt):
                  print("\n")
                  return
            else:
                  try:
                        run(c, stack=stack, variables=variables, macros=macros, raiseonexit=True)
                  except Exit as ext:
                        return

if __name__ == "__main__":
      from sys import argv, exit

      if argv[1:]:
            path, *args = argv[1:]

            try:
                  with open(path) as file:
                        contents = file.read()
            except (FileNotFoundError, PermissionError, OSError):
                  error(f"couldn't read file \"{path}\"")
                  exit(1)
            else:
                  try:
                        exit(run(contents, *args))
                  except KeyboardInterrupt:
                        exit(1)
                  except Exception as e:
                        raise e
                        error(f"{e} (python error)")
                        exit(1)
      else:
            repl(); exit(0)
