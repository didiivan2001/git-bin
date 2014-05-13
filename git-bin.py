#!/usr/bin/env python
import os.path
import argparse
import stat

import utils
import git
import commands as cmd


class Binstore(object):

    def __init__(self):
        pass

    def init(self):
        """ Initialize git-bin for this git repository."""
        raise NotImplemented

    def add_file(self, filename):
        """ Add the specified file to the binstore. """
        raise NotImplemented

    def edit_file(self, filename):
        """ Retrieve the specified file for editing. """
        raise NotImplemented

    def reset_file(self, filename):
        """ Reset the specified file. """

    def __contains__(self, item):
        """ Test whether a given item is in this binstore. The item may be a hash or a symlink in the repo """
        raise NotImplemented


class FilesystemBinstore(Binstore):

    def __init__(self, gitrepo, binstore_base):
        Binstore.__init__(self)
        self.gitrepo = gitrepo
        # retrieve the binstore path from the .git/config
        # TODO: what should we do if there is no path? It's a git-bin-init situation
        self.path = gitrepo.config.get("binstore", "path")
        if not self.path:
            self.init()

    def init(self):
        # TODO: create the ${binstore_base}/${repo} directory
        # TODO: create the .git/binstore symlink
        # TODO: set the settings in .git/config [binstore]
        # TODO: set self.path
        raise NotImplemented

    def add_file(self, filename):
        digest = utils.md5_file(filename)
        binstore_filename = os.path.join(self.path, digest)

        commands = cmd.CompoundCommand(
            [
                cmd.SafeMoveFileCommand(filename, binstore_filename),
                cmd.LinkToFileCommand(filename, binstore_filename),
                cmd.ChmodCommand(stat.S_IRUSR, stat.S_IRGRP, stat.S_IROTH, binstore_filename),
                cmd.GitAddCommand(self.gitrepo, filename),
            ]
        )

        commands.execute()

    def edit_file(self, filename):
        binstore_filename = os.readlink(filename)

        commands = cmd.CompoundCommand(
            [
                cmd.SafeMoveFileCommand(binstore_filename, filename, os.path.dirname(filename)),
            ]
        )

        commands.execute()

    def is_binstore_link(self, filename):
        if not os.path.islink(filename):
            return False

        if (os.readlink(filename).startswith(self.path) and
                self.has_file(os.readlink(filename))):
                return True

        return False


class GitBin(object):

    def __init__(self, binstore):
        self.binstore = binstore

    def add(self, filenames):
        # TODO: resolve globs, probably in the caller
        """ Add a list of files, specified by their full paths, to the binstore. """
        if not isinstance(filenames, list):
            filenames = [filenames]

        for filename in filenames:
            # if the file is a link, but the target is not in the binstore (i.e.
            # this was a real symlink originally), we can just add it. This check
            # is before the check for dirs so that we don't traverse symlinked dirs.
            if os.path.islink(filename) and not self.binstore.has_file(os.readlink(filename)):
                print "DO_GIT_ADD"
                continue

            if not utils.is_file_binary(filename):
                print "DO_GIT_ADD"
                continue

            if self.binstore.is_binstore_link(filename):
                # the file is already a symlink into the binstore. Nothing to do!
                return

            # if the filename is a directory, recurse into it.
            # TODO: maybe make recursive directory crawls optional/configurable
            if os.path.isdir(filename):
                for root, dirs, files in os.walk(filename):
                    # first add all directories recursively
                    self.add([os.path.join(root, dn) for dn in dirs])
                    # now add all the files
                    self.add([os.path.join(root, fn) for fn in files])
                return

            # at this point, we're only dealing with a file, so let's add it to the binstore
            self.binstore.add_file(filename)


def build_options_parser():
    parser = argparse.ArgumentParser(description='git bin')
    parser.add_argument(
        'command',
        choices=["add", "edit", "reset"],
        help='the command to perform')
    parser.add_argument(
        '-v', '--verbose',
        dest='verbose', action='store_true',
        default=False,
        help='be verbose')
    parser.add_argument(
        'files',
        type=str,
        nargs="+",
        metavar='FILE',
        help='the files on which to perform the command')

    return parser


# TODO:
# - implement git operations
# - impelement binstore
#       - use symlink in .git/ folder
#       - reverse lookups
# - implement offline/online commands
# - use a .gitbin file to store parameters
#       - init command?
#       - if file doesn't exist, suggest creating it on first use
#       - this file should be committed
# - detect online binstore available. if so, and was offline, suggest going online.
def main(args):
    binstore = Binstore()

if __name__ == '__main__':
    args = build_options_parser().parse_args()
    if args:
        main(args)
