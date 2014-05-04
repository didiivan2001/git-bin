import platform
import subprocess


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
