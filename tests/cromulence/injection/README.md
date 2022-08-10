# bryant

Bryce's first CHESS challenge

SQL-like injection fixable by using bound parameters.

## commands

* `LIST` - list of users
* `HELP` - list of commands
* `LOGIN username` - messages received by username
* `INBOX` - messages received by current user
* `SEND recipient` - start send flow to another user

## vulnerability

recipient checking in `SEND` command is injectable, allowing a malicious sender
to read arbitrary data

## BQL (bryant query language)

pronounced "bickle" like in taxi driver
