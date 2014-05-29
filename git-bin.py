#!/usr/bin/env python
import os.path
import argparse
import stat

import utils
import commands as cmd
import git


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

    def available(self):
        """ Test to see whether the binstore can be reached. """
        raise NotImplemented


class SSHFSBinstore(Binstore):
    pass


class FilesystemBinstore(Binstore):

    def __init__(self, gitrepo):
        Binstore.__init__(self)
        self.gitrepo = gitrepo
        # retrieve the binstore path from the .git/config
        # TODO: what should we do if there is no path? It's a git-bin-init situation
        self.localpath = os.path.join(self.gitrepo.path, ".git", "binstore")
        self.path = self.gitrepo.config.get("binstore", "path", None)
        if not self.path:
            self.init()

    def init(self):
        binstore_base = self.gitrepo.config.get("git-bin", "binstorebase", None)
        if not binstore_base:
            raise Exception("No git-bin.binstorebase is specified. You probably want to add this to your ~/.gitconfig")
        self.path = os.path.join(binstore_base, self.gitrepo.reponame)

        commands = cmd.CompoundCommand(
            cmd.MakeDirectoryCommand(self.path),
            cmd.LinkToFileCommand(self.localpath, self.path),
        )
        commands.execute()

        self.gitrepo.config.set("binstore", "path", self.path)

    def add_file(self, filename):
        digest = utils.md5_file(filename)
        binstore_filename = os.path.join(self.localpath, digest)

        # TODO: test for md5 collisions
        # TODO: make hash algorithm configurable

        commands = cmd.CompoundCommand(
            cmd.SafeMoveFileCommand(filename, binstore_filename),
            cmd.LinkToFileCommand(filename, binstore_filename),
            cmd.ChmodCommand(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH, binstore_filename),
            cmd.GitAddCommand(self.gitrepo, filename),
        )

        commands.execute()

    def edit_file(self, filename):
        binstore_filename = os.readlink(filename)

        commands = cmd.CompoundCommand(
            cmd.SafeMoveFileCommand(binstore_filename, filename, os.path.dirname(filename)),
        )

        commands.execute()

    def is_binstore_link(self, filename):
        if not os.path.islink(filename):
            return False

        if (os.readlink(filename).startswith(self.path) and
                self.has_file(os.readlink(filename))):
                return True

        return False


class UnknownCommandException(Exception):
    pass


class GitBin(object):

    def __init__(self, gitrepo, binstore):
        self.gitrepo = gitrepo
        self.binstore = binstore

    def dispatch_command(self, name, args):
        if not hasattr(self, name):
            raise UnknownCommandException("The command '%s' is not known to git-bin" % name)
        getattr(self, name)(args.files)

    def add(self, filenames):
        """ Add a list of files, specified by their full paths, to the binstore. """
        filenames = utils.expand_filenames(filenames)

        print "GitBin.add(%s)" % filenames
        for filename in filenames:
            print "\t%s" % filename

            if not os.path.exists(filename):
                print "'%s' did not match any files" % filename
                continue

            # if the file is a link, but the target is not in the binstore (i.e.
            # this was a real symlink originally), we can just add it. This check
            # is before the check for dirs so that we don't traverse symlinked dirs.
            if os.path.islink(filename) and not self.binstore.has_file(os.readlink(filename)):
                print "islink: DO_GIT_ADD"
                continue

            if not utils.is_file_binary(filename):
                self.gitrepo.add(filename)
                continue

            if self.binstore.is_binstore_link(filename):
                # the file is already a symlink into the binstore. Nothing to do!
                return

            # if the filename is a directory, recurse into it.
            # TODO: maybe make recursive directory crawls optional/configurable
            if os.path.isdir(filename):
                print "\trecursing into %s" % filename
                for root, dirs, files in os.walk(filename):
                    # first add all directories recursively
                    len(dirs) and self.add([os.path.join(root, dn) for dn in dirs])
                    # now add all the files
                    len(files) and self.add([os.path.join(root, fn) for fn in files])
                continue

            # at this point, we're only dealing with a file, so let's add it to the binstore
            self.binstore.add_file(filename)

    def reset(self, filenames):
        """ Reset a list of files """
        filenames = utils.expand_filenames(filenames)

        print "GitBin.reset(%s)" % filenames


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
    gitrepo = git.GitRepo(".")
    binstore = FilesystemBinstore(gitrepo)
    gitbin = GitBin(gitrepo, binstore)
    gitbin.dispatch_command(args.command, args)


if __name__ == '__main__':
    args = build_options_parser().parse_args()
    if args:
        main(args)
