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
        raise NotImplementedError

    def add_file(self, filename):
        """ Add the specified file to the binstore. """
        raise NotImplementedError

    def edit_file(self, filename):
        """ Retrieve the specified file for editing. """
        raise NotImplementedError

    def reset_file(self, filename):
        """ Reset the specified file. """

    def __contains__(self, item):
        """ Test whether a given item is in this binstore. The item may be a hash or a symlink in the repo """
        raise NotImplementedError

    def available(self):
        """ Test to see whether the binstore can be reached. """
        raise NotImplementedError


class SSHFSBinstore(Binstore):
    pass


class BinstoreException(Exception):
    pass


class FilesystemBinstore(Binstore):

    def __init__(self, gitrepo):
        Binstore.__init__(self)
        self.gitrepo = gitrepo
        # retrieve the binstore path from the .git/config

        # first look for the binstore base in the git config tree.
        binstore_base = self.gitrepo.config.get("git-bin", "binstorebase", None)
        # if that fails, try the environment variable
        binstore_base = binstore_base or os.environ.get("BINSTORE_BASE", binstore_base)
        if not binstore_base:
            raise BinstoreException("No git-bin.binstorebase is specified. You probably want to add this to your ~/.gitconfig")
        self.init(binstore_base)

    def init(self, binstore_base):
        self.localpath = os.path.join(self.gitrepo.path, ".git", "binstore")
        self.path = self.gitrepo.config.get("binstore", "path", None)
        if not self.path:
            self.path = os.path.join(binstore_base, self.gitrepo.reponame)

            commands = cmd.CompoundCommand(
                cmd.MakeDirectoryCommand(self.path),
                cmd.LinkToFileCommand(self.localpath, self.path),
            )
            commands.execute()

            self.gitrepo.config.set("binstore", "path", self.path)
        if not self.path.exists(self.path):
            raise BinstoreException("A binstore.path is set (%s), but it doesn't exist. Weird." % self.path)

    def get_binstore_filename(self, filename):
        """ get the real filename of a given file in the binstore. """
        # Note: this function assumes that the filename is in the binstore. You
        # probably want to check that first.
        if os.path.islink(filename):
            return os.readlink(filename)
        digest = utils.md5_file(filename)
        return os.path.join(self.localpath, digest)

    def has(self, filename):
        """ check whether a particular file is in the binstore or not. """
        if os.path.islink(filename):
            link_target = os.readlink(filename)
            if os.path.dirname(link_target) != self.localpath:
                return False
        return os.path.exists(self.get_binstore_filename(filename))

    def add_file(self, filename):
        binstore_filename = self.get_binstore_filename(filename)

        # TODO: test for md5 collisions
        # TODO: make hash algorithm configurable

        commands = cmd.CompoundCommand(
            cmd.SafeMoveFileCommand(filename, binstore_filename),
            cmd.LinkToFileCommand(filename, binstore_filename),
            cmd.ChmodCommand(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH,
                             binstore_filename),
            cmd.GitAddCommand(self.gitrepo, filename),
        )

        commands.execute()

    def edit_file(self, filename):
        print "edit_file(%s)" % filename
        print "binstore_filename: %s" % self.get_binstore_filename(filename)
        temp_filename = os.path.join(os.path.dirname(filename),
                                     ".tmp_%s" % os.path.basename(filename))
        print "temp_filename: %s" % temp_filename
        commands = cmd.CompoundCommand(
            cmd.CopyFileCommand(self.get_binstore_filename(filename),
                                temp_filename),
            cmd.SafeMoveFileCommand(temp_filename, filename),
        )

        commands.execute()

    def is_binstore_link(self, filename):
        if not os.path.islink(filename):
            return False

        print os.readlink(filename)
        print self.localpath

        if (os.readlink(filename).startswith(self.localpath) and
                self.has(os.readlink(filename))):
                return True

        return False


class CompatabilityFilesystemBinstore(FilesystemBinstore):

    def __init__(self, gitrepo):
        FilesystemBinstore.__init__(self, gitrepo)

    def init(self, binstore_base):
        self.path = os.path.join(binstore_base, self.gitrepo.reponame)
        self.localpath = self.path
        if not os.path.exists(self.path):
            raise BinstoreException("In compatibility mode, but binstore doesn't exist. What exactly are you trying to pull?")


class UnknownCommandException(Exception):
    pass


class GitBin(object):

    def __init__(self, gitrepo, binstore):
        self.gitrepo = gitrepo
        self.binstore = binstore

    def dispatch_command(self, name, arguments):
        if not hasattr(self, name):
            raise UnknownCommandException(
                "The command '%s' is not known to git-bin" % name)
        filenames = utils.expand_filenames(arguments.files)
        getattr(self, name)(filenames)

    def add(self, filenames):
        """ Add a list of files, specified by their full paths, to the binstore. """
        print "GitBin.add(%s)" % filenames
        for filename in filenames:
            print "\t%s" % filename

            if not os.path.exists(filename):
                print "'%s' did not match any files" % filename
                continue

            # if the file is a link, but the target is not in the binstore (i.e.
            # this was a real symlink originally), we can just add it. This
            # check is before the check for dirs so that we don't traverse
            # symlinked dirs.
            if os.path.islink(filename):
                if not self.binstore.is_binstore_link(filename):
                    # a symlink, but not into the binstore. Just add the link
                    # itself:
                    self.gitrepo.add(filename)
                # whether it's a binstore link or not, we can just continue
                continue

            if not utils.is_file_binary(filename):
                self.gitrepo.add(filename)
                continue

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

            # at this point, we're only dealing with a file, so let's add it to
            # the binstore
            self.binstore.add_file(filename)

    # normal git reset works like this:
    #   1. if the file is staged, it is unstaged. The file itself is untouched.
    #   2. if the file is unstaged, nothing happens.
    # To revert local changes in a modified file, you need to perform a
    # `checkout --`.
    #   1. if the file is staged, nothing happens.
    #   2. if the file is tracked and unstaged, it's contents are reset to the
    # value at head.
    #   3. if the file is untracked, an error occurs.
    # (see: http://git-scm.com/book/en/Git-Basics-Undoing-Things)
    #
    # legacy git-bin implemented the following logic:
    #   1. if the file is not binary (note that staged/unstaged is not
    # differentiated):
    #   1.1 if the file is added, a `git reset HEAD` is performed.
    #   1.2 if the file is modified, a `git checkout --` is performed.
    #   2. if the file is a binary file:
    #   2.1 if the file is added, the file is copied back from the binstore and
    # a `git reset HEAD` is performed.
    #   2.2 if the file is modified
    #   2.2.1 and its hash is in the binstore: a `git checkout --` is performed.
    #   2.2.1 but its hash is not in the binstore and there is a typechange, a
    # copy of the file is saved in /tmp and then the `git checkout --` is
    # performed.
    #
    # essentially we need two distinct operations:
    #   - unstage: just get it out of the index, but don't touch the file
    # itself.o
    #           For a binary file that has just been git-bin-add-ed, but was not
    # previously tracked, we will want to revert to the original file contents.
    # This more closely resembles the intention of the regular unstage operation
    #   - restore: change back to the contents at HEAD.
    #           For a binstore file this would mean switching back to the
    # symlink. If there was actually a modification, we also want to save a
    # 'just-in-case' file.
    # if we use the standard git nomenclature:
    #   - unstage -> reset
    #   - restore -> checkout --
    # let's implement these operations separately. We might implement a
    # compatibility mode.

    def reset(self, filenames):
        """ Unstage a list of files """
        print "GitBin.reset(%s)" % filenames
        for filename in filenames:

            # if the filename is a directory, recurse into it.
            # TODO: maybe make recursive directory crawls optional/configurable
            if os.path.isdir(filename):
                print "\trecursing into %s" % filename
                for root, dirs, files in os.walk(filename):
                    # first add all directories recursively
                    len(dirs) and self.reset([os.path.join(root, dn) for dn in dirs])
                    # now add all the files
                    len(files) and self.reset([os.path.join(root, fn) for fn in files])
                continue

            status = self.gitrepo.status(filename)
            if not status & git.STATUS_STAGED_MASK == git.STATUS_STAGED:
                # not staged, skip it.
                print "you probably meant to do: git bin checkout -- %s" % filename
                continue

            # unstage the file:
            self.gitrepo.unstage(filename)

            # key: F=real file; S=symlink; T=typechange; M=modified; s=staged
            # {1} ([F] -> GBAdded[Ss]) -> Untracked[S]
            # {2} ([S] -> GBEdit[TF] -> Modified[TF] -> GBAdded[MSs])
            #      -> Modified[MS]
            new_status = self.gitrepo.status(filename)

            if self.binstore.has(filename) and (
                    new_status & git.STATUS_UNTRACKED or
                    new_status & git.STATUS_MODIFIED):

                # TODO: in case {1} it's possible that we might be leaving an
                # orphan unreferenced file in the binstore. We might want to
                # deal with this.
                commands = cmd.CompoundCommand(
                    cmd.CopyFileCommand(
                        self.binstore.get_binstore_filename(filename),
                        filename),
                )
                commands.execute()

    def checkout_dashdash(self, filenames):
        """ Revert local modifications to a list of files """
        print "GitBin.checkout_dashdash(%s)" % filenames
        for filename in filenames:

            # if the filename is a directory, recurse into it.
            # TODO: maybe make recursive directory crawls optional/configurable
            if os.path.isdir(filename):
                print "\trecursing into %s" % filename
                for root, dirs, files in os.walk(filename):
                    # first add all directories recursively
                    len(dirs) and self.reset([os.path.join(root, dn) for dn in dirs])
                    # now add all the files
                    len(files) and self.reset([os.path.join(root, fn) for fn in files])
                continue

            status = self.gitrepo.status(filename)
            if status & git.STATUS_STAGED_MASK == git.STATUS_STAGED:
                # staged, skip it.
                print "you probably meant to do: git bin reset %s" % filename
                continue

            if not status & git.STATUS_CHANGED_MASK:
                # the file hasn't changed, skip it.
                continue

            # The first two cases can just be passed through to regular git
            # checkout --.
            # {1} (GBAdded[MSs] -> Reset[MS])
            # {2} (GBEdit[TF])
            # In the third case, there is some local modification that we should
            # save 'just in case' first.
            # {3} (GBEdit[TF] -> Modified[TF]) (*)

            if status & git.STATUS_TYPECHANGED and not self.binstore.has(filename):
                justincase_filename = os.path.join(
                    "/tmp",
                    "%s.%s.justincase" % (filename,
                                          self.binstore.digest(filename)))
                commands = cmd.CompoundCommand(
                    cmd.CopyFileCommand(
                        self.binstore.get_binstore_filename(filename),
                        justincase_filename),
                )
                commands.execute()

            self.gitrepo.restore(filename)

    def edit(self, filenames):
        """ Retrieve file contents for editing """
        print "GitBin.edit(%s)" % filenames
        for filename in filenames:

            # if the filename is a directory, recurse into it.
            # TODO: maybe make recursive directory crawls optional/configurable
            if os.path.isdir(filename):
                print "\trecursing into %s" % filename
                for root, dirs, files in os.walk(filename):
                    # first add all directories recursively
                    len(dirs) and self.reset([os.path.join(root, dn) for dn in dirs])
                    # now add all the files
                    len(files) and self.reset([os.path.join(root, fn) for fn in files])
                continue

            if os.path.islink(filename) and self.binstore.has(filename):
                self.binstore.edit_file(filename)


def build_options_parser():
    parser = argparse.ArgumentParser(description='git bin')
    parser.add_argument(
        'command',
        choices=["add", "edit", "reset", "checkout_dashdash"],
        help='the command to perform')
    parser.add_argument(
        '-v', '--verbose',
        dest='verbose', action='store_true',
        default=False,
        help='be verbose')
    parser.add_argument(
        '-d', '--debug',
        dest='debug', action='store_true',
        default=False,
        help='output debug info')
    parser.add_argument(
        '-C', '--compat',
        dest='compatibility', action='store_true',
        default=False,
        help='use compatibility mode for legacy gitbin symlink')
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
def print_exception(prefix, exception, verbose=False):
    print "%s: %s" % (prefix, exception)
    if verbose:
        import traceback
        traceback.print_exc()


def main(args):
    try:
        gitrepo = git.GitRepo()
        if args.compatibility:
            binstore = CompatabilityFilesystemBinstore(gitrepo)
        else:
            binstore = FilesystemBinstore(gitrepo)
        gitbin = GitBin(gitrepo, binstore)
        gitbin.dispatch_command(args.command, args)
    except git.GitException, e:
        print_exception("git", e, args.debug)
        exit(1)
    except BinstoreException, e:
        print_exception("binstore", e, args.debug)
        exit(1)


if __name__ == '__main__':
    args = build_options_parser().parse_args()
    if args:
        main(args)
