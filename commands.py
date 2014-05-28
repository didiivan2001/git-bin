import sys
import os
import shutil


class Command(object):

    def __init__(self):
        pass

    def execute(self, *args, **kwargs):
        raise NotImplemented()


class UndoableCommand(Command):

    def __init__(self):
        Command.__init__(self)

    def execute(self):
        try:
            return self._execute()
        except Exception:
            self.undo()
            exc_info = sys.exc_info()
            raise exc_info[1], None, exc_info[2]

    def _execute(self):
        raise NotImplemented()

    def undo(self):
        raise NotImplemented()


class CompoundCommand(Command):
    # TODO: this should really be an UndoableCommand
    # TODO: keep track of which commands completed successfully so that we can undo them if needs be

    def __init__(self, *args):
        self.commands = args

    def execute(self):
        for cmd in self.commands:
            cmd.execute()

    def push(self, command):
        self.commands.append(command)


class NotAFileException(BaseException):
    pass


class CopyFileCommand(Command):

    def __init__(self, src, dest):
        self.src = src
        self.dest = dest
        if not os.path.isfile(src):
            raise NotAFileException()

    def _execute(self):
        shutil.copy(self.src, self.dest)


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

    def __init__(self, src, dest, backupfile_dir=None):
        MoveFileCommand.__init__(self, src, dest)
        if not backupfile_dir:
            self.backupfile_dir = os.path.dirname(self.src)
        else:
            self.backupfile_dir = backupfile_dir

    def _execute(self):
        backup_filename = os.path.join(self.backupfile_dir, "._tmp_." + os.path.basename(self.src))
        # keep a copy of the files locally
        self.copy_cmd = CopyFileCommand(self.src, backup_filename)
        self.copy_cmd.execute()
        # move the file
        MoveFileCommand._execute(self)
        # remove the local copy
        os.remove(backup_filename)

    def undo(self):
        backup_filename = os.path.join(self.backupfile_dir, "._tmp_." + os.path.basename(self.src))
        shutil.move(backup_filename, self.src)


class LinkToFileCommand(Command):

    def __init__(self, linkname, targetname):
        self.linkname = linkname
        self.targetname = targetname

    def _execute(self):
        os.symlink(self.targetname, self.linkname)


class ChmodCommand(UndoableCommand):

    def __init__(self, modes, filename):
        self.modes = modes
        self.filename = filename

    def _execute(self):
        self.previous_modes = os.stat(self.filename).S_IMODE
        os.chmod(self.filename, self.modes)

    def undo(self):
        # TODO: it's conceivable that the modes were set and the user no longer
        # has permission to modify the modes. Not sure what to do in that case.
        os.chmod(self.filename, self.previous_modes)


class MakeDirectoryCommand(Command):

    def __init__(self, dirname, modes=0777):
        self.dirname, self.modes = dirname, modes

    def _execute(self):
        if not os.path.exists(self.dirname):
            os.makedirs(self.dirname, self.modes)

class GitAddCommand(UndoableCommand):

    def __init__(self, gitrepo, filename):
        self.gitrepo = gitrepo
        self.filename = filename

    def _execute(self):
        self.gitrepo.index.add(self.filename)

    def undo(self):
        self.gitrepo.index.remove(self.filename)
