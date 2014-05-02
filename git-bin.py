#!/usr/bin/env python
import os.path
import glob
import argparse
import subprocess
import platform

if platform.system() == "Darwin":
    md5_prog = "md5"
elif platform.system() == "Linux":
    md5_prog = "md5 --tag"


def call_prog(cmd, args):
    return subprocess.check_call([cmd] + args)


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
