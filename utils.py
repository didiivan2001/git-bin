import platform
import sh


def is_file_binary(filename):
    res = sh.file(filename, L=True, mime=True)
    if "charset=binary" in res or "charset=binary" in res:
        return True
    return False


if platform.system() == "Darwin":
    def md5_file(filename):
        res = sh.md5(filename)
        return res.rsplit("=")[1].strip()

elif platform.system() == "Linux":
    def md5_file(filename):
        res = sh.md5sum(filename, tag=True)
        return res.rsplit("=")[1].strip()
