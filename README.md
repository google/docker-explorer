# Docker Explorer

This project helps a forensics analyst explore offline Docker filesystems.

This is not an officially supported Google product.

If you're looking for similar capabilities on [Containerd](https://containerd.io/)
systems, feel free to check [https://github.com/google/container-explorer](https://github.com/google/container-explorer).

## Overview

When analyzing a system where a Docker container has been compromised, it can
be useful to have the same view of the filesystem as the container's.

Docker uses layered backend filesystems like
[AuFS](https://jpetazzo.github.io/assets/2015-03-03-not-so-deep-dive-into-docker-storage-drivers.html)
or OverlayFS.

Each layer is actually stored on the host's filesystem as multiple folders, and
some JSON files are used by Docker to know what is what;

## Installation

### PPA

A .deb package is available in the [GIFT PPA](https://launchpad.net/~gift)

```
add-apt-repository ppa:gift/stable
apt update
apt install docker-explorer-tools
```

### PyPI

This project is released on [PyPi](https://pypi.org/project/docker-explorer/).

```
virtualenv docker-explorer ; cd docker-explorer ; source bin/activate
pip install docker-explorer
```

### Source

You can clone this repository, as running the script doesn't require any
external dependency.

## Usage

For the forensicator, this usually goes:

0. find the interesting container ID
0. mount the container's filesystem in `/mnt/container`
0. `log2timeline.py /tmp/container.plaso /mnt/container`
0. or `ls -lta /mnt/container/tmp`

### List the running containers

On a live host running the compromised container you would run:

```
# docker ps
CONTAINER ID        IMAGE               COMMAND             CREATED         STATUS              PORTS               NAMES
7b02fb3e8a66        busybox             "sleep 10d"         19 hours ago    Up 19 hours                             dreamy_snyder
```

If you mount the disk image of the same host in `/mnt/root`, you can use `de.py`
to access the same information:

```
# de.py -r /mnt/root/var/lib/docker list running_containers
[
    {
        "container_id": "7b02fb3e8a665a63e32b909af5babb7d6ba0b64e10003b2d9534c7d5f2af8966",
        "image_id": "7968321274dc6b6171697c33df7815310468e694ac5be0ec03ff053bb135e768",
        "image_name": "busybox",
        "start_date": "2016-09-16T11:50:15.253796"
    }
]
```

### Mount the container's filesystem:

On a live host running the compromised container you would run:

```
# find ID of your running container:
docker ps

# create image (snapshot) from container filesystem
docker commit 12345678904b5 mysnapshot

# explore this filesystem using bash (for example)
docker run -t -i mysnapshot /bin/bash
```

If you mount the disk image of the same host in `/mnt/root`, you can use `de.py`
to access the same information:

```
# de.py -r /tmp/ mount 7b02fb3e8a665a63e32b909af5babb7d6ba0b64e10003b2d9534c7d5f2af8966 /tmp
You'll needs the aufs-tools package. If you install aufs-tools, I can run these for you.
```

Whoops... Let's try again

```
# apt install aufs-tools
# de.py -r /tmp/ mount 7b02fb3e8a665a63e32b909af5babb7d6ba0b64e10003b2d9534c7d5f2af8966 /tmp/test
mount -t aufs -o ro,br=/tmp/docker/aufs/diff/b16a494082bba0091e572b58ff80af1b7b5d28737a3eedbe01e73cd7f4e01d23=ro+wh none /tmp/test
mount -t aufs -o ro,remount,append:/tmp/docker/aufs/diff/b16a494082bba0091e572b58ff80af1b7b5d28737a3eedbe01e73cd7f4e01d23-init=ro+wh none /tmp/test
mount -t aufs -o ro,remount,append:/tmp/docker/aufs/diff/d1c54c46d331de21587a16397e8bd95bdbb1015e1a04797c76de128107da83ae=ro+wh none /tmp/test
root@test-VirtualBox:~# ls /tmp/test
bin  dev  etc  home  proc  root  sys  tmp  usr  var
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
{
    "sha256:7968321274dc6b6171697c33df7815310468e694ac5be0ec03ff053bb135e768": {
        "container_cmd": "/bin/sh -c #(nop)  CMD [\"sh\"]",
        "created_at : "2018-09-20T18:41:05.770133",
        "size" : 0
    }
}
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

## Maintainer notes

### Gift PPA push

Make sure the following is installed:
```
sudo apt install dh-python
```

For the GPG signing part, running over SSH with a gpg-agent running might
confuse gpg and ask for the passphrase on the $DISPLAY. To prevent this, you can
run `gpgconf --kill gpg-agent`.

Make a new version tag:
```
DATE="$(date +%Y%m%d)"
git checkout main
git pull upstream main
git tag "${DATE}"
git push upstream "${DATE}"
```

Build with [l2tdevtools](https://github.com/log2timeline/l2tdevtools).
```
cd /tmp
git clone https://github.com/log2timeline/l2tdevtools
```

Make the build environment:
```
mkdir /tmp/build
```

First we need 2 files, `post-dpkg-source.sh`:
```
cat <<EOF >post-dpkg-source.sh
PROJECT=\$1;
VERSION=\$2;
VERSION_SUFFIX=\$3;
DISTRIBUTION=\$4;
ARCHITECTURE=\$5;

dput ppa:docker-explorer-dev-team_staging ../\${PROJECT}_\${VERSION}-1\${VERSION_SUFFIX}~\${DISTRIBUTION}_\${ARCHITECTURE}.changes
EOF
```

and `prep-dpkg-source.sh`:
```
cat <<EOF >prep-dpkg-source.sh
export NAME="Docker-Explorer devs";
export EMAIL="docker-explorer-devs@google.com";

PROJECT=\$1;
VERSION=\$2;
VERSION_SUFFIX=\$3;
DISTRIBUTION=\$4;
ARCHITECTURE=\$5;

dch --preserve -v \${VERSION}-1\${VERSION_SUFFIX}~\${DISTRIBUTION} --distribution \${DISTRIBUTION} --urgency low "Modifications for PPA release."
EOF
```

These are also stored in `/tmp/build`

Then go to https://github.com/google/docker-explorer/releases and create a new
release.

Start the build:

```
PYTHONPATH=. python tools/build.py --build-directory=/tmp/build/  --project docker-explorer dpkg-source --distributions bionic,focal,jammy
```

Then upload the packages to the PPA:

```
dput ppa:docker-explorer-devs_staging docker-explorer_<VERSION>_source.changes
```

Then wait for launchpad to build the package, and move it from
ppa:docker-explorer-dev-team_staging to ppa:gift_stable, by going to
[https://launchpad.net/~docker-explorer-devs/+archive/ubuntu/staging/+copy-packages](https://launchpad.net/~docker-explorer-devs/+archive/ubuntu/staging/+copy-packages)




### Upload to PyPi

First make sure the proper version is set in `docker-explorer/__init__.py`.

Then run

```
python3 setup.py sdist
python3 -m twine upload  dist/*
```
