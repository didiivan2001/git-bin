import os.path
import os
from collections import OrderedDict


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
                    if not section_name in self.sections:
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
        if not section in self.sections:
            raise ValueError
        return self.sections[section].get(key, default)

    def set(self, section, key, value):
        if not section in self.sections:
            self.sections[section] = OrderedDict()
        self.sections[section][key] = value


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

if __name__ == "__main__":
    gr = GitRepo(".")
    gr.get_config().sections["binstore"]["test123"] = "test12345"
    gr.write_config()
