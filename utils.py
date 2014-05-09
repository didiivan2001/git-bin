import platform
import subprocess
import dulwich.repo
import os.path
import os


def call_prog(cmd, args):
    return subprocess.check_call([cmd] + args)


def is_file_binary(filename):
    res = call_prog("file", ["-L", "--mime", filename])
    if "charset=binary" in res or "charset=binary" in res:
        return True
    return False


if platform.system() == "Darwin":
    def md5_file(filename):
        res = call_prog("md5", [filename])
        return res.rsplit("=")[1].strip()

elif platform.system() == "Linux":
    def md5_file(filename):
        res = call_prog("md5sum", ["--tag", filename])
        return res.rsplit("=")[1].strip()


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


def get_repo(path=None):
    if not path:
        path = os.getcwd()
    root = find_repo_root(path)
    if root:
        return dulwich.repo.Repo(root)
    return None

