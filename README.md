gerrit-trac-hooks
============

master maybe doesn't work.
have a look at the tags.

## Features

- can be used for more than one trac instance
- every repo can be assigned to one trac instance (or/additionally you can use the catch-all mechanism)
- the following gerrit actions will be processed:
    - rewiew (+/- in green/red)
    - comments
    - patchsets (new/update)
    - merge
- processing of tags in commits (refs,see,fix,close,…) and perfomring related status changes in trac ticket (testing/closed/...)
- configuration through a config file

##Scheduled Features

- interaction with remote tracs (for the moment there is only support for local trac)
- advanced configuration (e.g. colors for trac comments and quotes, adaptions for what is the content of a trac comment, …)


## Install
1. `cd /path/to/your/gerrit/folder`
2. `sudo -u gerrit -H git clone https://github.com/xx4h/gerrit-trac-hooks.git hooks`
3. `cd hooks`
4. checkout what's the newest tag && `git checkout v0.1b`
5. `sudo -u gerrit -H cp hooks.config.example hooks.config`

now edit **hooks.config** to meet your needs

## Bugs & Features
There will be a Trac Instance for this in a few days =)


----------------------------------------------------------------------------
enjoy! =)

\\_ xx4h
