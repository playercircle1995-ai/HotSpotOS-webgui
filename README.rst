HotSpotOS
==========

.. image:: https://raw.githubusercontent.com/guysoft/HotSpotOS/devel/media/HotSpotOS.png
.. :scale: 50 %
.. :alt: HotSpotOS logo

A `Raspberry Pi <http://www.raspberrypi.org/>`_ distribution that makes a Raspberrypi start a hotspot, if no wifi was found to conenct to. It also bridges internet comming in from ethernet.
This repository contains the source script to generate the distribution out of an existing `RaspberryPi OS <https://www.raspberrypi.com/software/>`_ distro image. `You can download a built image here <http://unofficialpi.org/Distros/HotSpotOS>`_

The hotspot scripts are based on the `scripts by roboberry <http://www.raspberryconnect.com/network/item/330-raspberry-pi-auto-wifi-hotspot-switch-internet>`_ . And have been improved. They are part of the ``auto-hotspot`` module of CustomPiOS.
HotSpotOS is based on `CustomPiOS <https://github.com/guysoft/CustomPiOS>`_

Where to get it?
----------------

Official mirror is `here <http://unofficialpi.org/Distros/HotSpotOS>`_


How to use it?
--------------

#. Unzip the image and install it to an SD card `like any other Raspberry Pi image <https://www.raspberrypi.org/documentation/installation/installing-images/README.md>`_
#. If used as a wifi client, configure your WiFi by editing ``hotspotos-wpa-supplicant.txt`` on the root of the flashed card when using it like a flash drive
#. Boot the Pi from the SD card
#. If the image has found wifi then it will work like any RaspberryPi OS image. If it fails, or wifi is not set, it will start a wifi hotspot called "hotspot" which you can conncte to. Moreover, if an ethernet port is connected, it will bridge wifi and ethernet letting you connect to the internet.
#. If needed Log into your Pi via SSH (it is located at ``hotspot.lan`` `if your computer supports bonjour <https://learn.adafruit.com/bonjour-zeroconf-networking-for-windows-and-linux/overview>`_ or the IP address assigned by your router), default username is "pi", default password is "raspberry", change the password using the ``passwd`` command and expand the filesystem of the SD card through the corresponding option when running ``sudo raspi-config``.

Note: Local hostnames have the ``.lan`` domain ending. eg ``hotspot.lan``

Requirements
------------
* Raspberrypi 3 and newser or device running Armbian, Older Rasperry Pis are not currently supported.  See `Raspberry Pi <https://github.com/guysoft/FullPageOS/issues/12>`_ and `Raspberry Pi <https://github.com/guysoft/FullPageOS/issues/43>`_.
* 2A power supply


Features
--------

* Fails to connect to wifi, it will start a wifi hotspot named ``hotspot``, password ``raspberry``.
* Bridges between Ethernet and hotspot, which means if you connect the Pi to ethernet and set no wifi you will get a wifi hotspot to that ethernet network.
* IPv6 support with prefix delegation.
* Wifi settings can be done headless in ``hotspotos-wpa-supplicant.txt``
* Pi is avilable over the hotspot at IP hostname ``hotspot.lan``, on IPv4 ``192.168.50.1``.
* Supports Raspberry 3, 3B+ RaspberryPi Zero W.
* **Web dashboard** (added in this fork, see below) showing hotspot/wifi status and
  controls for an attached ADI Pluto+ SDR.

Web Dashboard & ADI Pluto+ SDR
-------------------------------

This fork adds a ``web-gui`` CustomPiOS module (``src/modules/web-gui``) that installs a
small Flask application, served on port 80 and enabled by default (``web-gui.service``).
Browse to ``http://hotspot.lan/`` (or the Pi's IP) to see:

* Current mode (Access Point vs Wifi client), SSID, interface IP, and a table of clients
  connected to the hotspot (MAC/IP/hostname/signal), read from ``hostapd``/``iw``/``dnsmasq``
  leases - no changes were made to the GPLv3 ``auto-hotspot`` module itself.
* "Rescan Wifi" / "Restart AP Services" buttons to nudge the auto-hotspot fallback logic.
* ADI Pluto+ SDR status (RX/TX LO frequency, sample rate, gain) and controls to change
  frequency, gain and sample rate, plus a live spectrum plot - via `pyadi-iio
  <https://github.com/analogdevicesinc/pyadi-iio>`_ / ``libiio``.
* A settings panel to change the Pluto connection URI (``ip:192.168.2.1`` by default for
  the Pluto's USB-gadget ethernet; use ``usb:X.Y.Z`` - see ``iio_info -s`` on the Pi - when
  connecting over plain USB).

You can change the default port and Pluto URI at build time by editing ``WEB_GUI_PORT`` /
``WEB_GUI_PLUTO_URI`` in ``src/config`` (or a ``src/config.local`` override); the Pluto URI
can also be changed at runtime from the dashboard's settings panel.

**Security note:** the dashboard has no authentication and runs as root (it needs root to
read hostapd/iw state and restart networking services). It is intended to only be reachable
over the hotspot's own subnet (``192.168.50.0/24``) - do not forward this port to an
untrusted network.

Developing
----------

Requirements
~~~~~~~~~~~~

#. `qemu-arm-static <http://packages.debian.org/sid/qemu-user-static>`_
#. `CustomPiOS <https://github.com/guysoft/CustomPiOS>`_
#. Downloaded `Raspbian <http://www.raspbian.org/>`_ image.
#. root privileges for chroot
#. Bash
#. realpath
#. sudo (the script itself calls it, running as root without sudo won't work)

Build HotSpotOS From within Raspbian / Debian / Ubuntu
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

HotSpot can be built from Debian, Ubuntu, Raspbian.
Build requires about 2.5 GB of free space available.
You can build it by issuing the following commands::

    sudo apt-get install realpath p7zip-full qemu-user-static
    
    git clone https://github.com/guysoft/CustomPiOS.git
    git clone https://github.com/guysoft/HotSpotOS.git
    cd HotSpotOS/src/image
    wget -c --trust-server-names 'https://downloads.raspberrypi.org/raspbian_lite_latest'
    cd ..
    ../../CustomPiOS/src/update-custompios-paths
    sudo modprobe loop
    sudo bash -x ./build_dist
    
Building HotSpotOS Variants
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

CustomPiOS supports building variants, which are builds with changes from the main release build. An example and other variants are available in the folder ``src/variants/example``.

To build a variant use::

    sudo bash -x ./build_dist [Variant]
    
Building Using Vagrant
~~~~~~~~~~~~~~~~~~~~~~
There is a vagrant machine configuration to let build HotSpotOS in case your build environment behaves differently. Unless you do extra configuration, vagrant must run as root to have nfs folder sync working.

To use it::

    sudo apt-get install vagrant nfs-kernel-server
    sudo vagrant plugin install vagrant-nfs_guest
    sudo modprobe nfs
    cd HotSpotOS/src/vagrant
    sudo vagrant up

After provisioning the machine, its also possible to run a nightly build which updates from devel using::

    cd HotSpotOS/src/vagrant
    run_vagrant_build.sh
    
To build a variant on the machine simply run::

    cd HotSpotOS/src/vagrant
    run_vagrant_build.sh [Variant]

Usage
~~~~~

#. If needed, override existing config settings by creating a new file ``src/config.local``. You can override all settings found in ``src/config``. If you need to override the path to the Raspbian image to use for building OctoPi, override the path to be used in ``ZIP_IMG``. By default, the most recent file matching ``*-raspbian.zip`` found in ``src/image`` will be used.
#. Run ``src/build_dist`` as root.
#. The final image will be created in ``src/workspace``

Building via GitHub Actions
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Since CustomPiOS needs ``qemu-user-static``, loop devices and root/chroot access (not
available on Windows or inside most sandboxes), this fork includes
``.github/workflows/build-image.yml``, which performs the same steps as the manual Debian
build above on an ``ubuntu-latest`` runner and uploads the resulting ``.img.xz`` as a build
artifact. Push this repo to GitHub and run the workflow from the Actions tab
(``workflow_dispatch``), or trigger it with the GitHub CLI::

    gh workflow run build-image.yml

Code contribution would be appreciated!


Attribution
~~~~~~~~~~~
The logo of HotSpotOS is a mix from the following icons:
1. https://icon-icons.com/icon/tech-ethernet/156953 (Dennis Suitters)  MIT License 
2. https://icon-icons.com/icon/internet-ethernet/103772 Jeremiah CC Atribution
3. https://pixabay.com/vectors/wireless-lan-ethernet-broadcast-304994/  Pixabay License (https://pixabay.com/service/license/)
