import os.path
import os
from collections import OrderedDict
import sh


# TODO: this is a little naive. When inside a submodule for example, we'll find
# the parent repo's root. Not sure what is the 'correct' behavior in this case.
def find_repo_root(path):
    if path.endswith(os.sep):
        path = path[:-1]

    while path not in ["", None, os.sep]:
        if os.path.exists(os.path.join(path, ".git")):
            break
        path, null = os.path.split(path)
    if path in ["", None, os.sep]:
        return None
    return path


class NotARepoException(Exception):
    pass


class GitConfig(object):

    """ Abstract base gitconfig class """

    def get(self, section, key, default=None):
        raise NotImplemented

    def set(self, section, key, value):
        raise NotImplemented


class GitFileConfig(GitConfig):

    def __init__(self, filename):
        self.filename = filename
        self.sections = OrderedDict()
        self.load()

    def load(self):
        # HACK: super naive implementation of git style config files.
        with open(self.filename, "rt") as f:
            current_section = None
            for line in f:
                line = line.strip()
                if not line:
                    continue

                if line.startswith("#"):
                    continue

                if line.startswith("["):
                    section_name = line[1:line.find("]")]
                    if section_name not in self.sections:
                        self.sections[section_name] = OrderedDict()
                    current_section = self.sections[section_name]
                elif "=" in line:
                    key, null, value = line.partition("=")
                    current_section[key.strip()] = value.strip()

    def write(self):
        data = ""
        for section_name, properties in self.sections.items():
            data += "[%s]\n" % section_name
            for key, value in properties.items():
                data += "\t%s = %s\n" % (key, value)
        with open(self.filename, "wt") as f:
            f.write(data)

    def get(self, section, key, default=None):
        if section not in self.sections:
            return default
        return self.sections[section].get(key, default)

    def set(self, section, key, value):
        if section not in self.sections:
            self.sections[section] = OrderedDict()
        self.sections[section][key] = value


class GitCommandConfig(GitConfig):

    def __init__(self, gitrepo):
        self.gitrepo = gitrepo
        self.git = sh.git.bake("--git-dir", os.path.join(self.gitrepo.path, ".git"))

    def get(self, section, key, default=None):
        try:
            return str(self.git.config("--get", "%s.%s" % (section, key))).strip()
        except sh.ErrorReturnCode:
            return default

    def set(self, section, key, value):
        self.git.config("%s.%s" % (section, key), value)


STATUS_UNTRACKED = 0x01
STATUS_STAGED = 0x02
STATUS_UNSTAGED = 0x04
STATUS_MODIFIED = 0x08
STATUS_DELETED = 0x10
STATUS_RENAMED = 0x20
STATUS_TYPECHANGED = 0x40
STATUS_ADDED = 0x80
STATUS_COPIED = 0x100

STATUS_STAGED_MASK = 0x6
STATUS_CHANGED_MASK = 0x1f8

status_map = {
    "M": STATUS_MODIFIED,
    "D": STATUS_DELETED,
    "R": STATUS_RENAMED,
    "T": STATUS_TYPECHANGED,
    "A": STATUS_ADDED,
    "C": STATUS_COPIED,
}


class UnknownGitStatusException:
    pass


class GitOperationException:
    pass


class GitRepo(object):

    def __init__(self, path):
        self.path = os.path.abspath(
            os.path.expandvars(
                os.path.expanduser(find_repo_root(path))
            )
        )
        self.shgit = sh.git.bake("--git-dir", os.path.join(self.path, ".git"))
        self.config = GitCommandConfig(self)
        remote_origin = self.config.get("remote.origin", "url", None)
        if remote_origin and ":" in remote_origin:
            self.reponame = remote_origin.strip().split(":")[1]
        else:
            self.reponame = os.path.basename(self.path)

    def status(self, filename):
        res = self.shgit.status(filename, porcelain=True)
        marker = res.strip()[:2]
        if marker == "??":
            return STATUS_UNTRACKED
        elif marker[0] == " ":
            ret = STATUS_UNSTAGED
            if not marker[1] in status_map:
                raise UnknownGitStatusException
            return ret | status_map[marker[1]]
        elif marker[1] == " ":
            ret = STATUS_STAGED
            if not marker[0] in status_map:
                raise UnknownGitStatusException
            return ret | status_map[marker[0]]

        raise UnknownGitStatusException

    def add(self, filename):
        res = self.shgit.add(filename)
        if res.exit_code:
            raise GitOperationException

    def unstage(self, filename, nocheck=False):
        status = self.status(filename)
        if not nocheck and status & STATUS_STAGED_MASK != STATUS_STAGED:
            # nothing to do.
            return
        res = self.shgit.reset(filename)
        if res.exit_code:
            raise GitOperationException

    def restore(self, filename):
        """ Restores a file to it's original value at HEAD."""
        status = self.status(filename)
        if not status & STATUS_CHANGED_MASK:
            # the file hasn't changed. There's nothing to restore
            # TODO: should we be unstaging at this point???
            return

        if status & STATUS_STAGED_MASK == STATUS_STAGED:
            self.unstage(filename, nocheck=True)
        res = sh.git.checkout("--", filename)
        if res.exit_code:
            raise GitOperationException

    def get_config(self):
        return self.config

    def write_config(self):
        self.config.write()

if __name__ == "__main__":
    gr = GitRepo(".")
    gr.get_config().sections["binstore"]["test123"] = "test12345"
    gr.write_config()