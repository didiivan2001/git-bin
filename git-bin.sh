BINSTORE=~/tmp/gitbin/binstore

function addbin {
    while [[ "x$1" != "x" ]];
    do
        src=$1 ; shift
        hash=`md5sum $src | cut -d" " -f1`
        # check whether the file is already a symlink to its hash in the binstore
        # i.e. there is nothing to reset
        [[ -L $src && "`readlink $src`" == "$BINSTORE/$hash" ]] && continue 

        echo "addbin: adding $src with hash $hash to $BINSTORE"

        if [[ -e $BINSTORE/$hash && `stat -c%s $BINSTORE/$hash` != `stat -c%s $src` ]]; then
            echo "addbin: SIGNATURE CONFLICT in $src!"
            echo "addbin: $src  in store has size `stat -c%s $BINSTORE/$hash`, and your file has size `stat -c%s $src`"
            return
        elif [[ -e $BINSTORE/$hash && -h $src ]]; then
            echo "addbin: nothing to do, $src is already in the binstore"
            return
        fi

        # BACKUP
        cp -f $src .tmp_$hash

        (cp -f $src $BINSTORE/$hash && rm -f $src && ln -s $BINSTORE/$hash $src && git add $src && rm -f .tmp_$hash) || (echo "addbin: something went wrong when adding $src, reverting" && mv -f .tmp_$hash $src)
    done
}

function editbin {
    while [[ "x$1" != "x" ]];
    do
        src=$1 ; shift
        storefile=`readlink $src`
        [[ $? == 1 || "$(dirname $storefile)" != "$BINSTORE" ]] && continue #not a symlink
        tmpfile=.tmp_$(basename $storefile)

        cp $storefile $tmpfile && mv -f $tmpfile $src && echo "editbin: $src is now available for editing"
    done
}

function resetbin {
    while [[ "x$1" != "x" ]];
    do
        src=$1 ; shift
        hash=`md5sum $src | cut -d" " -f1`
     
        # check whether the file is already a symlink to its hash in the binstore
        # i.e. there is nothing to reset
        [[ -L $src && "`readlink $src`" == "$BINSTORE/$hash" ]] && continue 

        if [[ ! -e $BINSTORE/$hash ]];
        then
            # The hash is not in the binstore. this could be because the file was never tracked by
            # git-bin, or because the file content has changed (following a git-bin-edit).
            # We test to see if the file was in git-bin by seeing if git-status lists it as having
            # had a type change (i.e. going from a symlink to a regular file). This will be the
            # status even if the file has also had its contents changed. If this is not the case,
            # we should just ignore the file as it's probably not a git-bin file.
            git status $src | grep -E "typechange: $src\$" 2>&1 >/dev/null || continue
            
            #otherwise, the file has changed, so we should back it up!
            echo "resetbin: $src has changed, saving a copy to /tmp/$src.$hash"
            cp -f $src /tmp/$src.$hash
        else
            # The has is in the binstore. We need to check for signature conflicts:
            if [[ `stat -c%s $BINSTORE/$hash` != `stat -c%s $src` ]]; then
                echo "resetbin: SIGNATURE CONFLICT in $src!"
                echo "resetbin: $src in store has size `stat -c%s $BINSTORE/$hash`, and your file has size `stat -c%s $src`"
                return
            fi
        fi
        # now we can just restore the file using git.
        echo "resetbin: restoring $src to the git HEAD"
        rm -f $src && git checkout -- $src
    done
}

funcname=$1 ; shift

case $funcname in
    add|edit|reset) 
        if [[ "x$1" == "x" ]];
        then
            echo "git bin: You must specify a file name to operate on!"
            exit 1
        fi
        eval ${funcname}bin $@
        ;;
    *) 
        echo "git-bin error: '$funcname' not a recognized command"
        echo "available commands are: add, edit, reset"
        ;;
esac
