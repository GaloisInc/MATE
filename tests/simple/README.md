# Examples

This directory contains programs that demonstrate the kinds of vulnerabilities
and properties we hope MATE will be able to reason about.


## registration

This program allows users to register with a username and (one-character)
password.

It has one good policy: it always sanitizes sensitive data (passwords) using a
"one way" function before outputting them.

It also has a fatal flaw: Although this option is not presented in the UI, any
logged-in user can switch to being logged in as any other user.

### query

Unfortunately, the code is not super well written, I/O is intermingled with
business logic. So to find the vulnerability in a query, we need to say not only
that the user logged in with `login`, but that they logged in with the right
username. That is,
```
let login       = function('login') in
let viewUser    = function('viewUser') in
let username    = valueOf('username').where(x -> x.inside(login)) in // symbolic
let currentUser = argumentsOf(viewUser)
controlFlowPathsBetween(login, viewUser)
  .excluding(login)
  .where(username != currentUser.name)
is empty
```
In English: There are no control-flow paths between `login` and `viewUser`
wherein the user has not logged in again, but the name of the active user has
changed.

### necessary data

 - Control flow queries (`controlFlowPathsBetween`), with ability to exclude
   certain paths from the query (`excluding`).
 - Assertions about (dis)equality of symbolic values (`!=`)

## matchmaker

This is one of the `cb-multios` challenges, see
[that directory](../tests/cb-multios) for build instructions.
The problem is that the service leaks information from a special memory location
called `FLAG_PAGE`.

### query

In reality, `FLAG_PAGE` is implemented as a C preprocessor macro. Unfortunately,
this makes it virtually invisible at the LLVM level. For now, let's pretend it's
a global variable by the same name.

```
let flag_page = globalVar('FLAG_PAGE') in
let outputs   = argumentsOf('output') in
dataFlowPathsBetween(flag_page[0-100], outputs) is empty
```
In english: There are no data-flow paths between the first 100 addresses after
the address `FLAG_PAGE` and the arguments of the output function.

### necessary data

Listing just what's above and beyond the above examples:

 - Ability to reason about dataflow from possibly symbolic pointers (and offsets
   from them)
 - Ability to reason about arithmetic relationships between pointers (ordering,
   equality, offsets)

[pidgin]: https://people.seas.harvard.edu/~chong/pubs/pldi15-pidgin.pdf
