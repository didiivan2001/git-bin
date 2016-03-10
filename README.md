# git-bin
git-bin is a tool which extends git to add simple and efficient tracking of binary files.

git-bin assumes that all users of a given repository have access to some shared
file-system, known as the `binstore`. This can be, for example, on an NFS share, or in a
remote directory mounted with sshfs.

The content of binary files is stored out-of-band in the `binstore`. When adding a
file to git-bin using the `git bin add` command, git-bin copies the contents of that file
to the shared `binstore` and replaces the file with a symlink to the original file in
the `binstore`. That symlink is then added to git. 

The symlink uses the md5 digest of the original file, so it is directly tied to the 
contents of that file. Changing the contents of the file will change the digest, 
and therefore the symlink. In this way, arbitrary binary files can be tracked through
different versions of the binary content.

git-bin has been tested and used extensively on Linux and OSX. Windows has not been
tested, but probably won't work due to the reliance on symlinks.

### Installing git-bin
At the moment, you can install git-bin by cloning the repo and running `python setup.py
install`.

### Specifying `binstore`
The base `binstore` used by git-bin can be set either by adding a `binstorebase` key in a
`git-bin` section in your repositories `.git/config` file, or by specifying the
`BINSTORE_BASE` environment variable.

When first using git-bin on a repository (by performing a `git bin init` or `git bin add`)
operation, a project-specific directory will be created in the `binstore` base directory
to contain all the binary file contents for this repo.

## Working with binary files
### Adding files
You can add a binary file to git by performing the `git bin add` command. This command has
the same semantics as the regular `git add` command. In particular it will recursively
add directories passed to it. `git add` is intelligent enough to inspect each target file
to determine whether it is actually a binary file, or if it might be a text file. If it is
a text file, it will be added to the cache using a standard git add.

You can safely `git bin add` a directory containing a mix of binary and text files, and
git-bin will only use out-of-band storage for the binary files.

### Editing files
If you want to edit a binary file, you're going to need its contents, not the symlink to
it.

You can retrieve the contents of a binary file using the `git bin edit` command. This
command will fetch the contents of the binary file from the `binstore`, and replace the
symlink with the actual contents. You can then modify the file and add the modified file
to git by doing another `git bin add`.

`git bin edit` can be reverted by doing a `git checkout --` on the edited file. This will
restore the symlink.

### Merging and conflicts
As there is no universal way to merge changes in arbitrary binary files, git-bin doesn't
really support a merge operation.

As only the symlinks are tracked, a merge conflict is expressed as a conflict in the
symlink itself. You can select the between the two symlinks to choose the content you wish
to keep.

Merging/conflicts has not been extensively tested. If you encounter a bug, please let us
know.

# Contacting us
You can contact us by opening a github issue on the project. We are also generally
available on irc on the freenode network in the #git-bin channel.

