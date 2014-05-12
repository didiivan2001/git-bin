import os.path
import os


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

    def __init__(self, filename):
        self.filename = filename
        self.load(filename)

    def load(self):
        raise NotImplemented

    def write(self):
        raise NotImplemented

    def get(self, section, key):
        raise NotImplemented

    def set(self, section, key, value):
        raise NotImplemented


class GitRepo(object):

    def __init__(self, path):
        self.path = os.path.abspath(
            os.path.expandvars(
                os.path.expanduser(find_repo_root(path))
            )
        )
        self.config = GitConfig(os.path.join(self.path, ".git", "config"))

    def status(self, filename):
        raise NotImplemented

    def add(self, filename):
        raise NotImplemented

    def unstage(self, filename):
        raise NotImplemented

    def get_config(self):
        return self.config

    def write_config(self):
        self.config.write()
