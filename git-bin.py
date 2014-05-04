#!/usr/bin/env python
import os.path
import glob
import argparse
import utils
import shutil
import sys


class Command(object):

    def __init__(self):
        pass

    def execute(self, *args, **kwargs):
        raise NotImplemented()


class UndoableCommand(Command):

    def __init__(self):
        Command.__init__(self)

    def execute(self, *args, **kwargs):
        try:
            return self._execute(*args, **kwargs)
        except Exception:
            self.undo()
            exc_info = sys.exc_info()
            raise exc_info[1], None, exc_info[2]

    def _execute(self, *args, **kwargs):
        raise NotImplemented()

    def undo(self):
        raise NotImplemented()


class NotAFileException(BaseException):
    pass


class CopyFileCommand(UndoableCommand):

    def __init__(self, src, dest):
        self.src = src
        self.dest = dest
        if not os.path.isfile(src):
            raise NotAFileException()

    def _execute(self):
        shutil.copy(self.src, self.dest)

    def undo(self):
        """ we don't need to do anything, as the copy does not damage the original """
        pass


class MoveFileCommand(UndoableCommand):

    def __init__(self, src, dest):
        self.src = src
        self.dest = dest
        if not os.path.isfile(src):
            raise NotAFileException()

    def _execute(self):
        # TODO: check for existance of dest and maybe abort? As it is, this
        # will automatically overwrite.
        shutil.move(self.src, self.dest)

    def undo(self):
        # TODO: perhaps check to see that the file was moved cleanly?
        shutil.move(self.dest, self.src)


class SafeMoveFileCommand(MoveFileCommand):

    def __init__(self, src, dest):
        MoveFileCommand.__init__(self, src, dest)

    def _execute(self):
        dirname = os.path.dirname(self.src)
        backup_filename = os.path.join(dirname, "._tmp_." + os.path.basename(self.src))
        # keep a copy of the files locally
        self.copy_cmd = CopyFileCommand(self.src, backup_filename)
        self.copy_cmd.execute()
        # move the file
        MoveFileCommand._execute(self)
        # remove the local copy
        os.remove(backup_filename)

    def undo(self):
        dirname = os.path.dirname(self.src)
        backup_filename = os.path.join(dirname, "._tmp_." + os.path.basename(self.src))
        shutil.move(backup_filename, self.src)


class Binstore(object):

    def __init__(self):
        pass

    def add_file(self, filename):
        raise NotImplemented


class FilesystemBinstore(Binstore):

    def __init__(self, path):
        Binstore.__init__(self)
        self.path = path

    def add_file(self, filename):
        commands = []

        digest = utils.md5_file(filename)
        binstore_filename = os.path.join(self.path, digest)

        commands.push(CopyFileCommand(filename, binstore_filename))


class FileInfo:

    def __init__(self, filename):
        self._filename = filename

    def basename(self):
        if self._filename[-1] == "/":
            return os.path.basename(self._filename[:-1])
        return os.path.basename(self._filename)

    def is_symlink(self):
        return os.path.islink(self._filename)

    def is_symlink_to_binstore(self):
        raise NotImplemented

    def is_dir(self):
        return os.path.isdir(self._filename)

    def is_binary(self):
        res = call_prog("file", ["-L", "--mime", self._filename])
        if "charset=binary" in res or "charset=binary" in res:
            return True
        return False

    def get_children(self, pattern):
        dirname = self._filename
        if dirname[-1] != "/":
            dirname += "/"
        glob.glob(dirname + pattern)

    def get_md5(self):
        res = call_prog(md5_prog, [self._filename])
        # parse the BSD style md5 tag:
        # MD5 (xxx) = 9a5c65d696bdaf75793b29c21c432107
        return res.rsplit("=")[1].strip()

    def get_hash(self):
        return self.get_md5()

    def size(self):
        return os.path.getsize(self._filename)

    def git_status(self):
        res = call_prog("git", ["--porcelain", self._filename])
        status_char, null, filename = res.strip().partition(" ")
        return status_char


class Binstore:

    def __init__(self, basedir):
        self._basedir = basedir

    def has_file(self, hash):
        raise NotImplemented

    def get_fileinfo(self, hash):
        raise NotImplemented

    def set_link(self, fo):
        raise NotImplemented

    def add_file(self, fo):
        raise NotImplemented


class Command:

    def __init__(self, binstore):
        self.binstore = binstore

    def perform(self, files):
        self._perform(files)

    def _perform(self, files):
        raise NotImplemented

    def _print(self, message):
        print message


class AddCommand(Command):

    def __init__(self, binstore):
        Command.__init__(self, binstore)

    def _perform(self, files):
        for f in files:
            fi = FileInfo(f)

            # if we're looking at the current dir, skip
            if fi.basename() == ".":
                continue

            # if the target file is a real symlink, i.e. one which doesn't point
            # into the binstore, just add it as is. This needs to be done before
            # the test for directory, so that we don't follow symlinked dirs.
            if fi.is_symlink() and fi.is_symlink_to_binstore():
                do_git_add
                continue

            # if the target file is a directory, we should add recursively.
            if fi.is_dir():
                self._print("descending into %s for recursive add." % f)
                self._perform(fi.get_children("*"))

            # if the target file is not a binary file, just add it
            if not fi.is_binary():
                do_git_add
                continue

            hash = fi.get_hash()

            # if the file hash already exists in the binstore, and the target file
            # is a symlink to it, there's nothing to do.
            if fi.points_to_binstore():
                continue

            self._print("adding %s with hash %s to binstore (%s)" % (f, hash, self.binstore))

            if self.binstore.has_file(hash):
                if self.binstore.get_fileinfo(hash).size() != fi.size():
                    # CONFLICT: same signature, different file size
                    raise Exception("Conflict")
                else:
                    # DUPLICATE: there were multiple copies of the same file in
                    # the original binary files.
                    self.binstore.set_link(fi, hash)

            self.binstore.add(fi, hash)


class EditCommand(Command):

    def __init__(self, binstore):
        Command.__init__(self, binstore)

    def _perform(self, files):
        for f in files:
            fi = FileInfo(f)

            # if the file is a directory, skip it as we don't allow recursive
            # edits
            if fi.is_dir():
                self._print("recursive edits are disabled for your safety and sanity")
                continue

            if fi.points_to_binstore(self.binstore):
                self.binstore.get_file(fi)


class ResetCommand(Command):

    def __init__(self, binstore):
        Command.__init__(self, binstore)

    def _perform(self, files):
        for f in files:
            fi = FileInfo(f)

            # if the file is a directory, skip it as we don't allow recursive
            # resets
            if fi.is_dir():
                self._print("recursive resets are disabled for your safety and sanity")
                continue

            status = fi.git_status()

            # if the file is not binary, just use the standard git operations
            if not fi.is_binary():
                do_git_reset

            if status == "A":
                # newly added file, not yet committed. Need to copy the actual
                # contents back and do a git reset HEAD
                pass
            elif status == "T":
                # type-change means we did a git bin edit (type changed from
                # symlink to real file). We can just do a git checkout --
                # if the file contents have changed, we should make a local backup
                pass
            else:
                # uh oh.
                raise Exception()


commands = {
    "add": AddCommand,
    "edit": EditCommand,
    "reset": ResetCommand,
}


def build_options_parser():
    parser = argparse.ArgumentParser(description='git bin')
    parser.add_argument(
        'command',
        choices=sorted(commands.keys()),
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
    if args.command in commands:
        commands[args.command](binstore)._perform(args.files)

if __name__ == '__main__':
    args = build_options_parser().parse_args()
    if args:
        main(args)
