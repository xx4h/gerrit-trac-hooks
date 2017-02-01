#!/usr/bin/python
#-*- coding: utf-8 -*-
#
# This is a set of gerrit hooks to interact with trac
# Copyright (C) 2014  Fabian 'xx4h' Melters
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA  02110-1301, USA.

import re
import os
import sys
import cgi
import magic

from optparse import OptionParser
from ConfigParser import RawConfigParser
from subprocess import Popen, PIPE, call
from datetime import datetime

## regex to find #TICKETNUMBER
TICKET_RE = re.compile('#([0-9]+)')

## remove substring from end of string
# thanks to http://stackoverflow.com/a/3663505/1922402
def rchop(thestring, ending):
    if thestring.endswith(ending):
        return thestring[:-len(ending)]
    return thestring


## execute git commands via Popen via call_git
def call_git(command, args, input=None):
    return Popen([TracGerritHookConfig().get('hook-settings', 'git_path'),
                  command] + args, stdin=PIPE,
                  stdout=PIPE).communicate(input)[0]


def call_pep(args=None):
    command_list = [TracGerritHookConfig().get('hook-settings', 'pep_path'),
                '--format="Line %(row)s (%(code)s): %(text)s"']
    if args:
        command_list.append(args)
    command_list.append('-')
    return Popen(command_list, stdin=PIPE, stdout=PIPE, stderr=PIPE)


def is_python(filename, code=None):
    if filename.endswith('.py'):
        return True
    elif filename.endswith('.pyc'):
        return False
    is_py = re.compile('(^|.*[\s/])python .*', re.IGNORECASE)
    ms = magic.open(magic.MAGIC_NONE)
    ms.load()
    return is_py.match(ms.buffer(code))


def check_pep_eight(filename, commit):
    """
    This functions receives a path to a file and checks the file
    type. If the file is a python file the function checks if the old
    version already was pep8, if this is true, it will be checked to
    match pep8
    """
    file_list = call_git('ls-tree', ['-r', commit + '^'])
    file_is_python = False
    files = []
    for line in file_list.splitlines():
        files.append(line.split()[-1:][0])
    if filename in files:
        orig_file = call_git('show', [commit + '^:' + filename])
        if is_python(filename, orig_file):
            file_is_python = True
            pep_call = call_pep()
            ret = pep_call.communicate(input=orig_file)[0]
            del orig_file
        else:
            del orig_file
            return (True, {filename: ['not a python file']})
    else:
        ret = ''

    # if ret is empty, it means that the old version had no pep8 errors
    # in this case we check the new version as well
    if not ret:
        commit_file = call_git('show', [commit + ':' + filename])
        if file_is_python or is_python(filename, commit_file):
            pep_call = call_pep()
            ret = pep_call.communicate(input=commit_file)[0]
            if ret:
                return (False, {filename: ret.splitlines()})
        else:
            return (True, {filename: ['not a python file']})
    return (True, {filename: ['PEP8-Check passed']})


class TracGerritHookConfig(RawConfigParser, object):
    '''
    '''
    def __init__(self, config_path=os.path.dirname(__file__) + '/hooks.config'):
        '''
        '''
        super(TracGerritHookConfig, self).__init__()
        # set default sections
        self.default_sections = ['hook-settings']

        # var init non default sections
        self.non_default_sections = []
        self.read(config_path)

    def set_defaults(self):
        '''
        '''
        for section in self.default_sections:
            # set defaults if section not present
            if not self.has_section(section):
                self.add_section(section)
            if section == 'hook-settings':
                if not self.has_option(section, 'use_default'):
                    self.set(section, 'use_default', True)
                if not self.has_option(section, 'git_path'):
                    self.set(section, 'git_path', '/usr/bin/git')
                if not self.has_option(section, 'pep_path'):
                    self.set(section, 'pep_path', '/usr/bin/pep8')
                if not self.has_option(section, 'python_egg_cache'):
                    self.set(section, 'python_egg_cache',
                                    '/var/trac/.egg-cache')
        return self


    def get_non_default_sections(self):
        '''
        '''
        self.set_defaults()
        for section in self.sections():
            if not (section == 'hook-settings'
               or section == 'trac-default'):
                self.non_default_sections.append(section)
        return self.non_default_sections

    def get_env_for_repo(self, repo):
        '''
        '''
        for section in self.get_non_default_sections():
            if self.has_option(section, 'repositories'):
                if repo in self.get(section,
                        'repositories').split('\n'):
                    if self.has_option(section, 'trac_env'):
                            return self.get(section, 'trac_env')
        if self.get('hook-settings', 'use_default') == 'True':
            if self.has_section('trac-default'):
                if self.has_option('trac-default','trac_env'):
                    return self.get('trac-default', 'trac_env')
        return None

    def get_section_for_repo(self, repo):
        '''
        '''
        for section in self.get_non_default_sections():
            if self.has_option(section, 'repositories'):
                if repo in self.get(section,
                        'repositories').split('\n'):
                    return section
        if self.get('hook-settings', 'use_default') == 'True':
            if self.has_section('trac-default'):
                return 'trac-default'

    def get_option_for_repo(self, repo_name, option):
        '''
        '''
        section = self.get_section_for_repo(repo_name)
        if self.has_option(section, option):
            return self.get(section, option)
        return None


class TracGerritTicket():
    '''
    '''

    def __init__(self, hook_name, options, config_path=None, debug=False):
        '''
        '''
        if not config_path:
            config_path = os.path.dirname(__file__) + '/hooks.config'
        self.config = TracGerritHookConfig(config_path)
        self.options = options
        self.options_dict = options.__dict__

        self.repo_name = self.options.project_name

        self.section = self.config.get_section_for_repo(self.repo_name)
        if self.config.has_option(self.section, 'comment_always'):
            self.comment_always = self.config.getboolean(self.section, 'comment_always')

        self.trac_env = self.config.get_env_for_repo(self.repo_name)
        if not self.trac_env:
            sys.exit(0)

	if self.trac_env.startswith("http"):
            self.trac_over_rpc = True
        else:
            self.trac_over_rpc = False
            self.env = open_environment(self.trac_env)

        self.hook_name = hook_name
        self.debug = debug

        self.commit_msg = ""

        ## make sure PYTHON_EGG_CACHE is set
        if not 'PYTHON_EGG_CACHE' in os.environ:
            os.environ['PYTHON_EGG_CACHE'] = self.config.\
                                                get('hook-settings',
                                                    'python_egg_cache')


    def get_built_comment(self, color):
        comment = self.options.comment.split('\n')
        color_line = "[[span(style=color: %s, %s)]]" % (color, comment[0])
        if len(comment) > 1:
            comment_line = "%s\n{{{#!html\n<blockquote class='citation'><p>%s\n\n</p></blockquote>\n}}}" \
                            % (color_line, cgi.escape('\n'.join(comment[1:])))
        else:
            comment_line = "%s\n\n" \
                            % (color_line)
        return comment_line

    def check_commit(self):
        print "***** running ref-update hook..."
        commit = self.options.newrev
        disable_ticketref = self.config.get_option_for_repo(
            self.options.project_name, 'disable_ticketref')
        if self.options.project_name in disable_ticketref:
            print("{0} does not need to reference a "
                "trac ticket number".format(self.options.project_name))
        else:
            ## check if root wants to commit
            name = call_git('show',['--format=%cn','-s',commit])
            if re.search("root", name, re.IGNORECASE):
                print "you are commiting as root - that is not allowed"
                sys.exit(1)
            ## if message references to a ticket it is ok
            message = call_git('show',['--format=%s%n%b','--summary',commit])
            if not re.search("(close|closed|closes|fix|fixed|fixes|references \
                             |refs|addresses|re|see) #[0-9]+",
                             message,re.IGNORECASE):
                if not re.search("(#noref|#release)",message,re.IGNORECASE):
                    print """
                    you need to reference a trac ticket number
                        command #1
                        command #1, #2
                        command #1 & #2
                        command #1 and #2
                    You can have more than one command in a message.
                    The following commands are supported. There is
                    more than one spelling for each command, to make
                    this as user-friendly as possible.

                    close, closed, closes, fix, fixed, fixes
                        The specified issue numbers are set to testing
                        with the contents of this commit message being
                        added to it.
                    references, refs, addresses, re, see
                        The specified issue numbers are left in their
                        current status, but the contents of this commit
                        message are added to their notes.

                    A fairly complicated example of what you can do is
                    with a commit message of:
                        Changed blah and foo to do this or that. Fixes #10
                        and #12, and refs #12.

                    This will close #10 and #12, and add a note to #12.\n"""
                    print "***** running ref-update hook... [ticketref failed]"
                    sys.exit(1)

        disable_pepcheck = self.config.get_option_for_repo(
            self.options.project_name, 'disable_pepcheck')
        if self.options.project_name in disable_pepcheck:
            print("{0} is disabled for pepcheck".format(
                self.options.project_name))
        else:
            # if more than one parent it is a merge and we ignore merges
            # in that case
            parents = call_git('cat-file', ['-p', commit]).splitlines()
            if (len(filter(lambda x: 'parent' in x, parents)) <= 1):
                files = call_git('diff', ['--name-only', commit + '^',
                    commit]).splitlines()
                pep_eight_check_success = True
                pep_dict_all = {}
                for filename in files:
                    if len(files) > 1 and re.search("debian/changelog", filename):
                        print("changelog ({0}) has to be a separate commit: {1}"
                              .format(filename, commit))
                        sys.exit(1)
                    good, pep_dict = check_pep_eight(filename, commit)
                    if not good:
                        pep_eight_check_success = False
                        pep_dict_all.update(pep_dict)
                    elif self.debug:
                        pep_dict_all.update(pep_dict)
                if not pep_eight_check_success:
                    print("PEP8 Errors found:\n=============================")
                    for filename in pep_dict_all.keys():
                        print("In '%s':" % filename)
                        for message in pep_dict_all[filename]:
                            print("-> %s" % message)
                    print("\nFor more information (all Files) run:")
                    print("    pep8 --repeat --statistics --show-source "
                            "--show-pep8 .")
                    print "***** running ref-update hook... [pep8 failed]"
                    sys.exit(1)
        print "***** running ref-update hook... [done]"


    def trac_merge_success(self):
        '''
        '''
        msg = "!Repo/Branch: %s/%s\n" \
              "[%s Gerrit Patchset merged]\n\n" \
              "%s\n\n" \
              "merged by %s" \
              % (self.repo_name,
                 self.options.branch_name,
                 self.options.change_url,
                 self.commit_msg,
                 self.options.submitter)
        return msg

    def trac_new_review(self):
        '''
        '''
        if self.options.review or re.search("Patch Set \d+: -Code-Review\n",
                                            self.options.comment):
            change_url_line = ""
            if self.options.review and int(self.options.review) > 0:
                comment_line = self.get_built_comment(color='green')
            elif not self.options.review:
                comment_line = self.get_built_comment(color='blue')
            else:
                comment_line = self.get_built_comment(color='red')
        else:
            comment = self.options.comment.split('\n')
            change_url_line = "[%s Comment]\n\n" % self.options.change_url
            comment_line = "Comment zu %s\n\n%s" % (comment[0],
                                                    '\n>'.join(comment[1:]))
        msg = "%s" \
              "%s" \
              % (change_url_line,
                 comment_line)
        return msg

    def trac_new_patchset(self):
        '''
        '''
        part_one, part_two = self.options.change_url.rsplit('/', 1)
        correct_change_url = "{0}/c/{1}".format(part_one, part_two)
        msg = "!Repo/Branch: %s/%s\n" \
              "[%s/%s Gerrit Patchset %s]\n\n" \
              "%s" \
              % (self.repo_name,
                 self.options.branch_name,
                 correct_change_url,
                 self.options.patchset,
                 self.options.patchset,
                 self.commit_msg)
        return msg


    ## handle communication with trac
    def handle_trac(self):
        if ('is_draft' in self.options_dict and
                self.options.is_draft == 'true'):
            return

	if self.trac_over_rpc:
            import xmlrpclib
        else:
            if not (os.path.exists(self.trac_env) and
                    os.path.isdir(self.trac_env)):
                print "trac_env (%s) is not a directory." % self.trac_env
                sys.exit(1)
            # trac specific imports
            from trac.ticket import Ticket
            from trac.env import open_environment
            from trac.ticket.notification import TicketNotifyEmail
            from trac.ticket.web_ui import TicketModule
            from trac.util.datefmt import utc


        # should never be used. but why not...
        if len(self.options.commit) == 0:
            return

        # get actual commit and extract ticket number(s)
        self.commit_msg = call_git('show',['--format=%s%n%b',
                                                '--summary',
                                                self.options.commit])

        # get author for trac comment
        if 'uploader' in self.options_dict and self.options.uploader:
            author = self.options.uploader
        elif 'author' in self.options_dict and self.options.author:
            author = self.options.author
        else:
            author = call_git('rev-list', ['-n',
                                            '1',
                                            self.options.commit,
                                            '--pretty=format:%an <%ae>']
                                    ).splitlines()[1]

        # find ticket numbers referenced in commit message
        ticket_numbers = TICKET_RE.findall(self.commit_msg)

        # create trac comment for every referenced ticket
        if (ticket_numbers):
            for ticket_id in ticket_numbers:

                if self.hook_name.endswith('patchset-created'):
                    msg = self.trac_new_patchset()
                elif self.hook_name.endswith('change-merged'):
                    msg = self.trac_merge_success()
                elif self.hook_name.endswith('comment-added'):
                    if self.comment_always:
                        msg = self.trac_new_review()
                    else:
                        if self.options.verified or self.options.review:
                            if self.options.verified_oldValue == None:
                                continue
                            elif self.options.review_oldValue == None:
                                continue
                        msg = self.trac_new_review()

                if self.debug:
                    print "you should be able to copy and paste the output " \
                          "to trac-comment-preview:"
                    print "---------------------------------------------------"
                    print "%s\n" % msg
                    print "---------------------------------------------------"
                    print "the author of the comment would be: %s"


                if self.trac_over_rpc:
                    try:
                        server = xmlrpclib.ServerProxy(self.trac_env)
                        ticket = {}
                        if self.hook_name.endswith('patchset-created'):
                            if re.search(
                                    "(close|closed|closes|fix|fixed|fixes) #" + \
                                    ticket_id, self.commit_msg, re.IGNORECASE):
                                ticket['status'] = "testing"
                        elif self.hook_name.endswith('change-merged'):
                                ticket['status'] = "closed"
                                ticket['resolution'] = "fixed"
                        server.ticket.update(int(ticket_id), msg, ticket,
                            True, author)

                    except Exception, e:
                        sys.stderr.write('Unexpected error while handling Trac ' \
                                         'ticket ID %s: %s (RPC)' \
                                         % (ticket_id, e))
                        
                else:
                    try:
                        db = self.env.get_db_cnx()
                        ticket = Ticket(self.env, ticket_id, db)
                        now = datetime.now(utc)

                        if self.hook_name.endswith('patchset-created'):
                            if re.search(
                                    "(close|closed|closes|fix|fixed|fixes) #" + \
                                    ticket_id, self.commit_msg, re.IGNORECASE):
                                ticket['status'] = "testing"
                        elif self.hook_name.endswith('change-merged'):
                                ticket['status'] = "closed"
                                ticket['resolution'] = "fixed"

                        cnum = 0
                        tm = TicketModule(self.env)
                        for change in tm.grouped_changelog_entries(ticket, db):
                            if change['permanent']:
                                cnum += 1

                        ticket.save_changes(author, msg, now, db, str(cnum+1))
                        db.commit()

                        tn = TicketNotifyEmail(self.env)
                        tn.notify(ticket, newticket=0, modtime=now)

                    except Exception, e:
                        sys.stderr.write('Unexpected error while handling Trac ' \
                                         'ticket ID %s: %s (MODULE)' \
                                         % (ticket_id, e))

