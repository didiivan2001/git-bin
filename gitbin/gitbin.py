#!/usr/bin/env python
'''
Usage:
    git-bin [-v] [--debug] <command> [--] <file>...
    git-bin init
    git-bin (-h|--help|--version)

Commands:
    add             store file in binstore and add it's link to the index
    edit            retrieve a file from the binstore for local edit
    checkout        restore the link to the last added version of the file
    init

Options:
    --help -h       print this help
    --version       print version and exit
    --verbose -v    enable verbose printing
    --debug         debug mode
'''
# '''
# Usage:
#     git-bin (add|edit|reset|checkout --) <file>...
#     git-bin (-h|--help|--version)
# '''
import os.path
import stat
import filecmp
import pkg_resources
from docopt import docopt

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
        """ Test whether a given item is in this binstore. The item may be a hash or a
        symlink in the repo """
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
            raise BinstoreException(
                "No git-bin.binstorebase is specified. You probably want to add this to" +
                " your ~/.gitconfig")
        self.init(binstore_base)

    def init(self, binstore_base):
        self.localpath = os.path.join(self.gitrepo.path, ".git", "binstore")
        self.path = os.path.join(binstore_base, self.gitrepo.reponame)

        if not os.path.exists(binstore_base):
            raise BinstoreException(
                ("The binstore base (%s) is inaccessible. Did you forget to mount" +
                 " something?") % binstore_base)
        if not os.path.exists(self.localpath):
            print "creating"
            commands = cmd.CompoundCommand(
                cmd.MakeDirectoryCommand(self.path),
                cmd.LinkToFileCommand(self.localpath, self.path),
            )
            commands.execute()

            # self.gitrepo.config.set("binstore", "path", self.path)
        if not os.path.exists(self.path):
            raise BinstoreException(
                "A binstore.path is set (%s), but it doesn't exist. Weird." % self.path)

    def get_binstore_filename(self, filename):
        """ get the real filename of a given file in the binstore. """
        # Note: this function assumes that the filename is in the binstore. You
        # probably want to check that first.
        if os.path.islink(filename):
            # return os.readlink(filename)
            return os.path.realpath(filename)
        digest = utils.md5_file(filename)
        return os.path.join(self.localpath, digest)

    def has(self, filename):
        """ check whether a particular file is in the binstore or not. """
        if os.path.islink(filename):
            link_target = os.path.realpath(filename)
            if os.path.dirname(link_target) != os.path.realpath(self.localpath):
                return False
        return os.path.exists(self.get_binstore_filename(filename))

    def add_file(self, filename):
        binstore_filename = self.get_binstore_filename(filename)

        # TODO: make hash algorithm configurable

        # relative link is needed, here, so it points from the file directly to
        # the .git directory
        relative_link = os.path.relpath(binstore_filename, os.path.dirname(filename))
        #  create only a link if file already exists in binstore
        if os.path.exists(binstore_filename):
            print('WARNING: File with that hash already exists in binstore.')
            if filecmp.cmp(filename, binstore_filename):
                print('         Creating a link to existing file')
                commands = cmd.CompoundCommand(
                    cmd.SafeRemoveCommand(filename),
                    cmd.LinkToFileCommand(filename, relative_link),
                    cmd.GitAddCommand(self.gitrepo, filename),
                )
            else:
                raise ValueError('hash collision found between %s and %s',
                                 filename, binstore_filename)
        else:
            commands = cmd.CompoundCommand(
                cmd.SafeMoveFileCommand(filename, binstore_filename),
                cmd.LinkToFileCommand(filename, relative_link),
                cmd.ChmodCommand(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH,
                                 binstore_filename),
                cmd.GitAddCommand(self.gitrepo, filename),
            )

        commands.execute()

    def edit_file(self, filename):
        printv("edit_file(%s)" % filename)
        printv("binstore_filename: %s" % self.get_binstore_filename(filename))
        temp_filename = os.path.join(os.path.dirname(filename),
                                     ".tmp_%s" % os.path.basename(filename))
        printv("temp_filename: %s" % temp_filename)
        commands = cmd.CompoundCommand(
            cmd.CopyFileCommand(self.get_binstore_filename(filename),
                                temp_filename),
            cmd.SafeMoveFileCommand(temp_filename, filename, noprogress=True),
            cmd.ChmodCommand(stat.S_IRUSR | stat.S_IWUSR |
                             stat.S_IRGRP | stat.S_IWGRP |
                             stat.S_IROTH | stat.S_IWOTH,
                             filename),
        )

        commands.execute()

    def is_binstore_link(self, filename):
        if not os.path.islink(filename):
            return False

        printv(os.readlink(filename))
        printv(self.localpath)

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
            raise BinstoreException(
                "In compatibility mode, but binstore doesn't exist. What exactly are" +
                " you trying to pull?")


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
        filenames = utils.expand_filenames(arguments['<file>'])
        getattr(self, name)(filenames)

    def add(self, filenames):
        """ Add a list of files, specified by their full paths, to the binstore. """
        printv("GitBin.add(%s)" % filenames)
        for filename in filenames:
            printv("\t%s" % filename)

            # we want to add broken symlinks as well
            if not os.path.lexists(filename):
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

            # TODO: maybe create an empty file with some marking
            # now we just skip it
            if utils.is_file_pipe(filename):
                continue

            # if the filename is a directory, recurse into it.
            # TODO: maybe make recursive directory crawls optional/configurable
            if os.path.isdir(filename):
                printv("\trecursing into %s" % filename)
                for root, dirs, files in os.walk(filename):
                    # now add all the files
                    len(files) and self.add([os.path.join(root, fn) for fn in files])
                continue

            # at this point, we're only dealing with a file, so let's add it to
            # the binstore
            self.binstore.add_file(filename)

    def init(self, args):
        pass

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
        printv("GitBin.reset(%s)" % filenames)
        for filename in filenames:

            # if the filename is a directory, recurse into it.
            # TODO: maybe make recursive directory crawls optional/configurable
            if os.path.isdir(filename):
                printv("\trecursing into %s" % filename)
                for root, dirs, files in os.walk(filename):
                    # first reset all directories recursively
                    len(dirs) and self.reset([os.path.join(root, dn) for dn in dirs])
                    # now reset all the files
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

    def checkout(self, filenames):
        """ Revert local modifications to a list of files """
        printv("GitBin.checkout(%s)" % filenames)
        for filename in filenames:

            # if the filename is a directory, recurse into it.
            # TODO: maybe make recursive directory crawls optional/configurable
            if os.path.isdir(filename):
                printv("\trecursing into %s" % filename)
                for root, dirs, files in os.walk(filename):
                    # first checkout_dashdash all directories recursively
                    len(dirs) and self.checkout([os.path.join(root, dn) for dn in dirs])
                    # now checkout_dashdash all the files
                    len(files) and self.checkout([os.path.join(root, fn) for fn in files])
                continue

            status = self.gitrepo.status(filename)
            if (status & git.STATUS_STAGED_MASK) == git.STATUS_STAGED:
                # staged, skip it.
                print "you probably meant to do: git bin reset %s" % filename
                continue

            if not (status & git.STATUS_CHANGED_MASK):
                # the file hasn't changed, skip it.
                continue

            # The first two cases can just be passed through to regular git
            # checkout --.
            # {1} (GBAdded[MSs] -> Reset[MS])
            # {2} (GBEdit[TF])
            # In the third case, there is some local modification that we should
            # save 'just in case' first.
            # {3} (GBEdit[TF] -> Modified[TF]) (*)

            if (status & git.STATUS_TYPECHANGED) and not self.binstore.has(filename):
                justincase_filename = os.path.join(
                    "/tmp",
                    "%s.%s.justincase" % (filename,
                                          utils.md5_file(filename)))
                commands = cmd.CompoundCommand(
                    cmd.CopyFileCommand(
                        self.binstore.get_binstore_filename(filename),
                        filename,
                        justincase_filename),
                )
                commands.execute()

            self.gitrepo.restore(filename)

    def edit(self, filenames):
        """ Retrieve file contents for editing """
        printv("GitBin.edit(%s)" % filenames)
        for filename in filenames:

            # if the filename is a directory, recurse into it.
            # TODO: maybe make recursive directory crawls optional/configurable
            if os.path.isdir(filename):
                printv("\trecursing into %s" % filename)
                for root, dirs, files in os.walk(filename):
                    # first edit all directories recursively
                    len(dirs) and self.edit([os.path.join(root, dn) for dn in dirs])
                    # now edit all the files
                    len(files) and self.edit([os.path.join(root, fn) for fn in files])
                continue

            if os.path.islink(filename) and self.binstore.has(filename):
                self.binstore.edit_file(filename)


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


def get_binstore(repo):
    return FilesystemBinstore(repo)


printv = utils.printv


def _main(args):
    try:
        gitrepo = git.GitRepo()
        binstore = get_binstore(gitrepo)
        gitbin = GitBin(gitrepo, binstore)
        cmd = args['<command>']

        if args['--verbose']:
            utils.VERBOSE = True

        if args['init']:
            gitbin.dispatch_command('init', args)
        elif cmd is not None:
            gitbin.dispatch_command(cmd, args)

    except git.GitException, e:
        print_exception("git", e, args['--debug'])
        print(__doc__)
        exit(1)
    except BinstoreException, e:
        print_exception("binstore", e, args['--debug'])
        exit(1)
    except UnknownCommandException, e:
        print(__doc__)
        exit(1)
    except KeyboardInterrupt:
        exit(1)


def main():
    version = pkg_resources.require("gitbin")[0].version
    args = docopt(__doc__, version=version, options_first=True)
    if args:
        _main(args)


if __name__ == '__main__':
    main()
