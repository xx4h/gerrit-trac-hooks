gerrit-trac-hooks
============
a project by [xx4h Public Projects](https://pp.xx4h.de/) (_sorry_, _i_ _can_ _not_ _afford_ _a_ _trusted_ _cert_)

[![Build Status](https://jenkins.xx4h.de/job/gerrit-trac-hooks/badge/icon)](https://jenkins.xx4h.de/job/gerrit-trac-hooks/) (_sorry_, _i_ _can_ _not_ _afford_ _a_ _trusted_ _cert_)  

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
4. checkout what's the newest tag && `git checkout v0.12b`
5. **optional:** edit `config_path` in change-merged, comment-added, patchset-created and ref-update
6. `sudo -u gerrit -H cp hooks.config.example hooks.config`

now edit **hooks.config** to meet your needs

## Bugs & Features
[Closed Bugs/Features](https://pp.xx4h.de/report/10)
[Open Bugs/Features](https://pp.xx4h.de/report/9)
[Create New Issue/Bug/Feature](https://pp.xx4h.de/newticket)


----------------------------------------------------------------------------
enjoy! =)

\\_ xx4h
