#!/usr/bin/python
#-*- coding: utf-8 -*-
#
# This is a set of gerrit hooks to interact with trac
# Copyright (C) 2013  Fabian 'xx4h' Melters
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

from optparse import OptionParser
from ConfigParser import RawConfigParser
from subprocess import Popen, PIPE, call
from datetime import datetime

# trac specific imports
from trac.ticket import Ticket
from trac.env import open_environment
from trac.ticket.notification import TicketNotifyEmail
from trac.ticket.web_ui import TicketModule
from trac.util.datefmt import utc


## remove substring from end of string
# thanks to http://stackoverflow.com/a/3663505/1922402
def rchop(thestring, ending):
    if thestring.endswith(ending):
        return thestring[:-len(ending)]
    return thestring


## regex to find #TICKETNUMBER
TICKET_RE = re.compile('#([0-9]+)')


class TracGerritHookConfig(RawConfigParser, object):
    '''
    '''
    def __init__(self):
        '''
        '''
        super(TracGerritHookConfig, self).__init__()
        # set default sections
        self.default_sections = ['hook-settings']

        # var init non default sections
        self.non_default_sections = []

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
        if self.get('hook-settings', 'use_default'):
            if self.has_section('trac-default'):
                if self.has_option('trac-default','trac_env'):
                    return self.get('trac-default', 'trac_env')
        return None


class TracGerritTicket():
    '''
    '''

    def __init__(self, hook_name, options, config_path=None, debug=False):
        '''
        '''
        self.config = TracGerritHookConfig()
        if not config_path:
            config_path = os.path.dirname(__file__) + '/hooks.config'
        self.config.read(config_path)
        self.options = options

        self.repo_name = self.options.project_name

        self.trac_env = self.config.get_env_for_repo(self.repo_name)
        if not self.trac_env:
            sys.exit(0)

        self.env = open_environment(self.trac_env)

        self.hook_name = hook_name
        self.debug = debug

        self.commit_msg = ""

        ## make sure PYTHON_EGG_CACHE is set
        if not 'PYTHON_EGG_CACHE' in os.environ:
            os.environ['PYTHON_EGG_CACHE'] = self.config.\
                                                get('hook-settings',
                                                    'python_egg_cache')

    ## execute git commands via Popen via call_git
    def call_git(self, command, args, input=None):
        return Popen([self.config.get('hook-settings', 'git_path'),
                      command] + args, stdin=PIPE,
                      stdout=PIPE).communicate(input)[0]

    def get_built_comment(self, color):
        comment = self.options.comment.split('\n')
        color_line = "[[span(style=color: %s, %s)]]" % (color, comment[0])
        if len(comment) > 1:
            comment_line = "%s\n%s\n\n" \
                            % (color_line, '\n>'.join(comment[1:]))
        else:
            comment_line = "%s\n\n" \
                            % (color_line)
        return comment_line

    def check_for_ticket_reference(self):
        print "***** running ref-update hook..."

        commit = self.options.newrev
        ## check if root wants to commit
        name = self.call_git('show',['--format=%cn','-s',commit])
        if re.search("root", name, re.IGNORECASE):
            print "you are commiting as root - that is not allowed"
            sys.exit(1)
        ## if message references to a ticket it is ok
        message = self.call_git('show',['--format=%s%n%b','--summary',commit])
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
                sys.exit(1)
        print "***** running ref-update hook... [done]"

    def trac_merge_success(self):
        '''
        '''
        msg = "Repo: %s\n" \
              "Branch: %s\n" \
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
            if self.options.review and int(self.options.review) > 0:
                change_url_line = "[%s Gerrit Review]\n\n" \
                                    % self.options.change_url
                comment_line = self.get_built_comment(color='green')
            elif not self.options.review:
                change_url_line = "[%s Gerrit Review]\n\n" \
                                   % self.options.change_url
                comment_line = self.get_built_comment(color='blue')
            else:
                change_url_line = "[%s Gerrit Review]\n\n" \
                                   % self.options.change_url
                comment_line = self.get_built_comment(color='red')
        else:
            change_url_line = "[%s Comment]\n\n" % self.options.change_url
            comment_line = "Comment zu %s\n\n" % self.options.comment
        msg = "Repo: %s\n" \
              "Branch: %s\n" \
              "%s" \
              "%s" \
              "Commit: \n%s" \
              % (self.repo_name,
                 self.options.branch_name,
                 change_url_line,
                 comment_line,
                 self.commit_msg)
        return msg

    def trac_new_patchset(self):
        '''
        '''
        msg = "Repo: %s\n" \
              "Branch: %s\n" \
              "Patchset Nr.: %s\n" \
              "[%s Gerrit Patchset]\n\n" \
              "%s" \
              % (self.repo_name,
                 self.options.branch_name,
                 self.options.patchset,
                 self.options.change_url,
                 self.commit_msg)
        return msg


    ## handle communication with trac
    def handle_trac(self):
        if not (os.path.exists(self.trac_env) and
                os.path.isdir(self.trac_env)):
            print "trac_env (%s) is not a directory." % self.trac_env
            sys.exit(1)

        # should never be used. but why not...
        if len(self.options.commit) == 0:
            return

        # get actual commit and extract ticket number(s)
        self.commit_msg = self.call_git('show',['--format=%s%n%b',
                                                '--summary',
                                                self.options.commit])

        # get author for trac comment
        author = self.call_git('rev-list', ['-n',
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
                    msg = self.trac_new_review()


                if self.debug:
                    print "you should be able to copy and paste the output " \
                          "to trac-comment-preview:"
                    print "---------------------------------------------------"
                    print "%s\n" % msg
                    print "---------------------------------------------------"
                    print "the author of the comment would be: %s"


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
                                     'ticket ID %s: %s' \
                                     % (ticket_id, e))

