# Docker Explorer

This project helps a forensics analyst explore offline Docker filesystems.

This is not an officially supported Google product.

## Overview

When analyzing a system where a Docker container has been compromised, it can
be useful to have the same view of the filesystem as the container's.

Docker uses layered backend filesystems like
[AuFS](https://jpetazzo.github.io/assets/2015-03-03-not-so-deep-dive-into-docker-storage-drivers.html)
or OverlayFS.

Each layer is actually stored on the host's filesystem as multiple folders, and
some JSON files are used by Docker to know what is what;

## Usage

For the forensicator, this usually goes:

0. find the interesting container ID
0. mount the container's filesystem in `/mnt/aufs`
0. `log2timeline.py /tmp/container.plaso /mnt/aufs`

### List the running containers

On the live host:

```
# docker ps
CONTAINER ID        IMAGE               COMMAND             CREATED         STATUS              PORTS               NAMES
7b02fb3e8a66        busybox             "sleep 10d"         19 hours ago    Up 19 hours                             dreamy_snyder
```

On a disk image mounted in
`/mnt/root`:

```
# de.py -r /mnt/root/var/lib/docker list running_containers
Container id: 7b02fb3e8a665a63e32b909af5babb7d6ba0b64e10003b2d9534c7d5f2af8966 / Labels :
    Start date: 2017-02-13T16:45:05.785658046Z
    Image ID: 7968321274dc6b6171697c33df7815310468e694ac5be0ec03ff053bb135e768
    Image Name: busybox
```

### Mount the container's filesystem:

On the live host:

```
# find ID of your running container:
docker ps

# create image (snapshot) from container filesystem
docker commit 12345678904b5 mysnapshot

# explore this filesystem using bash (for example)
docker run -t -i mysnapshot /bin/bash
```

On a disk image mounted in
`/mnt/root`:

```
# de.py -r /tmp/ mount 7b02fb3e8a665a63e32b909af5babb7d6ba0b64e10003b2d9534c7d5f2af8966 /tmp
You'll needs the aufs-tools package. If you install aufs-tools, I can run these for you.
```

Whoops... Let's try again

```
# apt-get install aufs-tools
# de.py -r /tmp/ mount 7b02fb3e8a665a63e32b909af5babb7d6ba0b64e10003b2d9534c7d5f2af8966 /tmp/test
mount -t aufs -o ro,br=/tmp/docker/aufs/diff/b16a494082bba0091e572b58ff80af1b7b5d28737a3eedbe01e73cd7f4e01d23=ro+wh none /tmp/test
mount -t aufs -o ro,remount,append:/tmp/docker/aufs/diff/b16a494082bba0091e572b58ff80af1b7b5d28737a3eedbe01e73cd7f4e01d23-init=ro+wh none /tmp/test
mount -t aufs -o ro,remount,append:/tmp/docker/aufs/diff/d1c54c46d331de21587a16397e8bd95bdbb1015e1a04797c76de128107da83ae=ro+wh none /tmp/test
Do you want to mount this container Id: /tmp/docker/aufs/diff/b16a494082bba0091e572b58ff80af1b7b5d28737a3eedbe01e73cd7f4e01d23 on /tmp/test?
      (ie: run these commands) [Y/n]

root@test-VirtualBox:~# ls /tmp/test
bin  dev  etc  home  proc  root  sys  tmp  usr  var
```


### List the available images

On the live host:

```
# docker images
REPOSITORY          TAG                 IMAGE ID            CREATED       SIZE
busybox             latest              7968321274dc        4 weeks ago   1.11 MB
```

On a disk image mounted in
`/mnt/root`:

```
# de.py -r /mnt/root/var/lib/docker list repositories
Listing repositories from file /tmp/docker/image/aufs/repositories.json
{
    "Repositories": {
        "busybox": {
            "busybox:latest": "sha256:7968321274dc6b6171697c33df7815310468e694ac5be0ec03ff053bb135e768"
        }
    }
}
```

### Show a container's image history

On the live host:

```
# docker history 7968321274dc6b6171697c33df7815310468e694ac5be0ec03ff053bb135e768
IMAGE               CREATED             CREATED BY                                      SIZE                COMMENT
7968321274dc        4 weeks ago         /bin/sh -c #(nop)  CMD ["sh"]                   0 B
<missing>           4 weeks ago         /bin/sh -c #(nop) ADD file:707e63805c0be1a226   1.11 MB
```


On a disk image mounted in
`/mnt/root`:

```
# de.py -r /mnt/root/var/lib/docker history 7b02fb3e8a665a63e32b909af5babb7d6ba0b64e10003b2d9534c7d5f2af8966
--------------------------------------------------------------
sha256:7968321274dc6b6171697c33df7815310468e694ac5be0ec03ff053bb135e768
        size : 0
        created at : 2017/01/13 22:13:54
        with command : /bin/sh \
-c \
#(nop)  \
CMD ["sh"]
```

## Troubleshooting

If on your Ubuntu system you get the errors:

```
mount: unknown filesystem type 'aufs'
/sbin/mount.aufs:proc_mnt.c:96: /mnt/aufs: Invalid argument
/sbin/mount.aufs:proc_mnt.c:96: /mnt/aufs: Invalid argument
/sbin/mount.aufs:proc_mnt.c:96: /mnt/aufs: Invalid argument
/sbin/mount.aufs:proc_mnt.c:96: /mnt/aufs: Invalid argument
/sbin/mount.aufs:proc_mnt.c:96: /mnt/aufs: Invalid argument
/sbin/mount.aufs:proc_mnt.c:96: /mnt/aufs: Invalid argument
/sbin/mount.aufs:proc_mnt.c:96: /mnt/aufs: Invalid argument
/sbin/mount.aufs:proc_mnt.c:96: /mnt/aufs: Invalid argument
/sbin/mount.aufs:proc_mnt.c:96: /mnt/aufs: Invalid argument
....
```

Try this:

```
sudo apt-get install linux-image-extra-$(uname -r)
```
