import sh
import os.path
import hashlib


def is_file_binary(filename):
    res = sh.file(filename, L=True, mime=True)
    if "charset=binary" in res or "charset=binary" in res:
        return True
    return False


def md5_file(filename):
    chunk_size = 4096
    state = hashlib.md5()
    f = open(filename, 'rb')
    buff = f.read(chunk_size)
    while len(buff):
        state.update(buff)
        buff = f.read(chunk_size)
    f.close()
    return state.hexdigest()


def expand_filenames(filenames):
    """ expands the filenames, resolving environment variables, ~ and globs """
    res = []

    for filename in filenames:
        filename = os.path.expandvars(os.path.expanduser(filename))
        if any((c in filename) for c in "?*["):
            res += sh.glob(filename)
        else:
            res += [filename]
    return res


def are_same_filesystem(file1, file2):
    """ Test if the files are on the same file-system. """
    return os.stat(file1).st_dev == os.stat(file2).st_dev
