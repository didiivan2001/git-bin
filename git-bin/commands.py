import sys
import os
import shutil
from utils import printv

try:
    import progressbar

    PROGRESSBAR_MINIMUM_SIZE = 1024 * 1024 * 10
    PROGRESSBAR_BLOCK_SIZE = 1024 * 16
except ImportError:
    progressbar = None


class Command(object):

    def __init__(self):
        pass

    def execute(self):
        self._execute()

    def _execute(self):
        raise NotImplemented

    def __repr__(self):
        return object.__repr__(self)


class UndoableCommand(Command):

    def __init__(self):
        Command.__init__(self)

    def execute(self):
        try:
            return self._execute()
        except Exception, e:
            print "Exception occurred: %s" % e
            print "Undoing..."
            self.undo()
            exc_info = sys.exc_info()
            raise exc_info[1], None, exc_info[2]

    def _execute(self):
        raise NotImplemented()

    def undo(self):
        raise NotImplemented

    def cleanup(self):
        pass


class CompoundCommand(UndoableCommand):
    # TODO: this should really be an UndoableCommand
    # TODO: keep track of which commands completed successfully so that we can undo them
    # if needs be

    def __init__(self, *args):
        self.commands = args
        self.executed_commands = []

    def _execute(self):
        for cmd in self.commands:
            printv(cmd)
            cmd.execute()
            self.executed_commands.append(cmd)
        self.cleanup()

    def undo(self):
        print "undo: %s" % self.executed_commands
        while len(self.executed_commands):
            cmd = self.executed_commands.pop()
            if not isinstance(cmd, UndoableCommand):
                continue
            print "undoing %s" % cmd
            try:
                cmd.undo()
            except Exception:
                print "\nException while undoing %s" % cmd
                import traceback
                traceback.print_exc()
                print "Continuing to undo other commands ...\n"

    def cleanup(self):
        while len(self.executed_commands):
            cmd = self.executed_commands.pop()
            if not isinstance(cmd, UndoableCommand):
                continue
            printv("cleaning up %s" % cmd)
            cmd.cleanup()

    def push(self, command):
        self.commands.append(command)


class NotAFileException(BaseException):
    pass


class CopyFileCommand(Command):

    def __init__(self, src, dest, noprogress=False):
        self.src = src
        self.dest = dest
        self.noprogress = noprogress
        if not os.path.isfile(src):
            raise NotAFileException()

    def _execute(self):
        size = os.path.getsize(self.src)
        if not self.noprogress and progressbar and size > PROGRESSBAR_MINIMUM_SIZE:
            pb = progressbar.ProgressBar(widgets=[progressbar.Bar(),
                                                  progressbar.Percentage(),
                                                  " | ",
                                                  progressbar.ETA()], maxval=size)
            pb.start()
            copied_size = 0
            with open(self.src, 'rb') as src:
                with open(self.dest, 'wb') as dest:
                    while copied_size < size:
                        data = src.read(PROGRESSBAR_BLOCK_SIZE)
                        dest.write(data)
                        copied_size += len(data)
                        pb.update(copied_size)
            pb.finish()
        else:
            shutil.copy(self.src, self.dest)
        shutil.copystat(self.src, self.dest)

    def __repr__(self):
        return "%s(%s, %s)" % (self.__class__.__name__, self.src, self.dest)


class MoveFileCommand(UndoableCommand):

    def __init__(self, src, dest, noprogress=False):
        self.src = src
        self.dest = dest
        self.noprogress = noprogress

    def _execute(self):
        # TODO: check for existance of dest and maybe abort? As it is, this
        # will automatically overwrite.
        size = os.path.getsize(self.src)
        if not self.noprogress and progressbar and size > PROGRESSBAR_MINIMUM_SIZE:
            pb = progressbar.ProgressBar(widgets=[progressbar.Bar(),
                                                  progressbar.Percentage(),
                                                  " | ",
                                                  progressbar.ETA()], maxval=size)
            pb.start()
            copied_size = 0
            tmpdest = self.dest + ".tmp"
            with open(self.src, 'rb') as src:
                with open(tmpdest, 'wb') as dest:
                    while copied_size < size:
                        data = src.read(PROGRESSBAR_BLOCK_SIZE)
                        dest.write(data)
                        copied_size += len(data)
                        pb.update(copied_size)
            pb.finish()

            shutil.copystat(self.src, tmpdest)
            shutil.move(tmpdest, self.dest)
            os.remove(self.src)
        else:
            shutil.move(self.src, self.dest)

    def undo(self):
        # TODO: perhaps check to see that the file was moved cleanly?
        shutil.move(self.dest, self.src)

    def __repr__(self):
        return "%s(%s, %s)" % (self.__class__.__name__, self.src, self.dest)


class SafeMoveFileCommand(MoveFileCommand):

    def __init__(self, src, dest, backupfile_dir=None, noprogress=False):
        MoveFileCommand.__init__(self, src, dest, noprogress)
        if not backupfile_dir:
            self.backupfile_dir = os.path.dirname(self.src)
        else:
            self.backupfile_dir = backupfile_dir

    def _execute(self):
        self.backup_filename = os.path.join(
            self.backupfile_dir,
            "._tmp_." + os.path.basename(self.src))
        # keep a copy of the files locally
        self.copy_cmd = CopyFileCommand(self.src, self.backup_filename, noprogress=True)
        self.copy_cmd.execute()
        # move the file
        MoveFileCommand._execute(self)

    def undo(self):
        shutil.move(self.backup_filename, self.src)
        os.remove(self.dest)

    def cleanup(self):
        # remove the local copy
        os.remove(self.backup_filename)


class LinkToFileCommand(UndoableCommand):

    def __init__(self, linkname, targetname):
        self.linkname = linkname
        self.targetname = targetname

    def _execute(self):
        os.symlink(self.targetname, self.linkname)

    def undo(self):
        os.remove(self.linkname)

    def __repr__(self):
        return "%s(%s, %s)" % (self.__class__.__name__, self.targetname, self.linkname)


class SafeRemoveCommand(MoveFileCommand):

    def __init__(self, filename):
        dest = "._tmp_." + os.path.basename(filename)
        super(SafeRemoveCommand, self).__init__(filename, dest)

    def cleanup(self):
        os.remove(self.dest)


class ChmodCommand(UndoableCommand):

    def __init__(self, modes, filename):
        self.modes = modes
        self.filename = filename
        self.previous_modes = 0

    def _execute(self):
        self.previous_modes = os.stat(self.filename).st_mode
        os.chmod(self.filename, self.modes)

    def undo(self):
        # TODO: it's conceivable that the modes were set and the user no longer
        # has permission to modify the modes. Not sure what to do in that case.
        os.chmod(self.filename, self.previous_modes)

    def __repr__(self):
        return "%s(%s, %o)" % (self.__class__.__name__, self.filename, self.modes)


class MakeDirectoryCommand(Command):

    def __init__(self, dirname, modes=0777):
        self.dirname, self.modes = dirname, modes

    def _execute(self):
        if not os.path.exists(self.dirname):
            os.makedirs(self.dirname, self.modes)

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, self.dirname)


class GitAddCommand(UndoableCommand):

    def __init__(self, gitrepo, filename):
        self.gitrepo = gitrepo
        self.filename = filename

    def _execute(self):
        self.gitrepo.add(self.filename)

    def undo(self):
        self.gitrepo.unstage(self.filename)

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, self.filename)


class GitUnstageCommand(UndoableCommand):

    def __init__(self, gitrepo, filename):
        self.gitrepo = gitrepo
        self.filename = filename

    def _execute(self):
        self.gitrepo.unstage(self.filename)

    def undo(self):
        self.gitrepo.add(self.filename)

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, self.filename)


class GitRetoreCommand(UndoableCommand):

    def __init__(self, gitrepo, filename, justincase_filename):
        self.gitrepo = gitrepo
        self.filename = filename
        self.justincase_filename = justincase_filename

    def _execute(self):
        self.gitrepo.restore(self.filename)

    def undo(self):
        MoveFileCommand(self.justincase_filename, self.filename).execute()

    def __repr__(self):
        return "%s(%s, %s)" % (self.__class__.__name__, self.filename,
                               self.justincase_filename)
