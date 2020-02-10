#!/bin/bash

# Note of the commands required to build a Debian package.

package=etrial-manager
version=0.2.0

if [ -d "$package-$version" ]; then
  rm -r "$package-$version"
fi

# use the contents of the deb directory as a skeleton
cp -r deb $package-$version

# fill it out with the required parts of the repo
mkdir -p $package-$version/usr/share/$package
cp app.py $package-$version/usr/share/$package
cp -r templates $package-$version/usr/share/$package
cp -r static $package-$version/usr/share/etrial-manager
cp -r scripts $package-$version/usr/share/etrial-manager

# build the package
dpkg -b $package-$version $package-$version.deb
rm -r "$package-$version"
