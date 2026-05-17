# yams

Stack-based RPN metaprogramming language implemented in Python. Leisure project.

## Usage (`yams.py`)

When called without arguments, it will run a REPL. Elsewise, it will read a file from the first argument and give it the remaining ones as `argv`. You should use the `.yams` file extension.

## Basics

### “Hello, word” program

```yams
" Hello, world. " println
```

### Datatypes

- Numbers.
- Lists.
- Words.
- Word lists (`words`).
- `null`

### Code execution

Use the `do` word to execute a word list.

```yams
( " Hello. " println ) do
```

### Variables and macros

Words can be quoted. You can use a quoted word and a value to define variables (or macros if te value is a word list).

```yams
'pi 3.14159 define
'double ( 2 * ) macro

'var pi double define
```

### Functions

Functions are defined with the `function` keyword. They're just fancier macros (with inputs).

```yams
'square ( x ) (
  x x *
) function define

2 square do tostr println
```

### Comments

Comments are delimited by `/*` and `*/`. Remember the space between them and the actual comment inside (`/*comment*/` is not valid but `/* comment */` is).

```yams
/*
  greetings
*/
```

### Other words

```
do        /* executes a word-list or a function */
readln    /* reads a string */
import    /* imports yams file as word-list */
if        /* returns b if a, else c */
cond      /* executes b if a */
boolean   /* 1 if x else 0 */
error     /* raises an error with a message and an exit code */
exit      /* exits the program with a code */
goto      /* replaces the rest of the program with the given word-list */
self      /* returns the source program as a word-list */
```

#
