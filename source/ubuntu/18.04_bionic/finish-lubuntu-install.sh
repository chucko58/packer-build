#! /bin/bash
# Provisioning script for Lubuntu-lite VMs

if [ "$(whoami)" != 'root' ] ; then
    echo This script must be run as root. Exiting.
    exit 1
fi

# Exit on error
set -e

# Get directory containing this script
here="$(cd "$(dirname "${BASH_SOURCE[${#BASH_SOURCE[@]}-1]}")" && pwd -P)"
if [ -z "$here" ] || [ ! -d "$here" ]
then
    echo 'Error: unable to determine path to script, exiting'
    exit 1
fi

. "$here"/robust_execute.sh

echo 'APT::Acquire::Retries "5";' > /etc/apt/apt.conf.d/80-retries

# Common error with apt-get install
robust_execute_re='403  Forbidden'

apt_get_install_opts='-q -y'
apt_get_purge_opts='-q -y --auto-remove'

# Clean up unneeded packages
apt-get $apt_get_purge_opts purge aspell gstreamer1.0-gl gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-pulseaudio gstreamer1.0-x libpulse0 libpulsedsp pavucontrol pulseaudio pulseaudio-utils ubuntu-report wireless-tools yelp

# Update s/w databases
apt-get -q update

# Upgrade the installed s/w
robust_execute apt-get -q -y dist-upgrade

# Add essential GUI pieces
robust_execute apt-get $apt_get_install_opts --no-install-recommends install emacs25 emacs25-el file-roller fonts-inconsolata fonts-liberation firefox

# Delete anything that is no longer required
apt-get -q -y --purge autoremove 

# Clean the package DB
apt-get -q autoclean
