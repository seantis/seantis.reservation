**THIS README IS A WORK IN PROGRESS**

seantis.reservation
===================

A Plone addon to manage resources through reservations.

Introduction
------------

Originally developed together with the municipality of Zug, Switzerland this
Addon aims to combine differing reservation systems into one flexible solution.

It does so by providing a way to deal with the following usecases:

 * Manage meeting rooms in a company. Users reserve the rooms themselves
   without an authority confirming/denying their reservations.

 * Manage nursery spots. Parents apply for a spot in the nursery for their kid.
   Someone at the nursery goes through the applicants and decides who gets
   the spot. Parents may add an application to the waitinglist.

 * Manage community facilities. Citizens see the availability of facilities
   online and call the municipality to reserve a facility. The management
   is done internally (maybe through an already existing software). The addon
   is used in a read only fashion.

Screenshots
-----------


Requirements
------------

- Python 2.7
- Linux / Posix ( Windows may or may not work )
- Postgresql 9.1+ ( Older versions DO NOT work! )
- 1024MB+ RAM

seantis.reservation is tested using IE8+, Chrome, Firefox. IE7 is not supported!
Note also that IE8 and IE9 only work right if the Plone site is in production
mode. The reason for it is that those browsers ignore every stylesheet after the
32th. In production these stylesheets are merged.

Recommended Packages
--------------------

seantis.reservation is best used together with seantis.dir.facility. Said package
enables the creation of a directory of facilities. Say a directory of rooms, 
or a directory of nurseries. Or a directory of community college courses.

A facility directory will display an overview containing a calendar, a map and
some management tools. This overview is part of seantis.reservation and may
be used in other products, but that will require some work and a deeper understanding
of Plone.

seantis.reservation may be used on its own, but throughout this readme it is assumed
that seantis.dir.facility is installed alongside.

Installation
------------

The setup instructions assume an Ubuntu / Debian Server installation as well
as basic knowledge of Plone.

## Install required packages

    sudo apt-get install git-core
    sudo apt-get install libxml2 libxml2-dev
    sudo apt-get install libxslt1.1 libxslt1-dev
    sudo apt-get install pyhton2.7
    sudo apt-get install python2.7-dev

## Install Postgresql

Run the installer

    sudo apt-get install postgresql-9.1
    sudo apt-get install postgresql-9.1-dev

Create a database user (replace `your_password` with your own). This password is
needed later!

    sudo -u postgres psql -c "CREATE USER reservation WITH PASSWORD 'your_password'"

Create the reservations database

    sudo -u postgres psql -c "CREATE DATABASE reservations ENCODING 'UTF8' TEMPLATE template0"

Grant the required privileges to the reservation user

    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE reservations to reservation"

## Install Plone

Download the buildout configs to the folder which will hold your Plone installation. 
    
    wget -qO - https://raw.github.com/seantis/seantis.reservation/master/buildout/buildouts.sh | bash

Or if you don't have wget (like on OSX):

    curl https://raw.github.com/seantis/seantis.reservation/master/buildout/buildouts.sh | bash 

Edit your database connection settings in the database.cfg file.

    nano database.cfg

Download the boostrap script

    wget http://python-distribute.org/bootstrap.py

Again, alternatively with curl

    curl http://python-distribute.org/bootstrap.py > bootstrap.py

Bootstrap your environment

    python2.7 bootstrap.py

Run the installation (and get that coffee machine cracking)

*Note that due to seantis.reservation being under heavy development, you must 
currently use develop.cfg instead of the usual buildout.cfg*

    bin/buildout -c develop.cfg

If everything went well you may now start your instance

    bin/instance fg

## Creating a Reservation Plone Site

### Create the Site

Having started your instance, navigate to the plone root:

    http://localhost:8080

It should say 'Plone is up and running'. On this site click "Create new Plone site"
If you used the develop.cfg the username and password are "admin" and "admin".

Obviously you do not want to use develop.cfg in production!

On the "Create a Plone site" form, you should enter name and title of your
plone site, followed by checking the boxes of the following Add-Ons:

 * Collective Geo Contentlocations
 * Collective Geo Geographer
 * Collective Geo Kml
 * Collective Geo MapWidget
 * Collective Geo Openlayers
 * Collective Geo Settings
 * seantis.dir.facility
 * seantis.reservation

Having done that, click "Create Plone Site"

### Create a Facility Directory

On your freshly minted Plone Site, click on "Add new..." and choose 
"Facility Directory". For this introduction we shall create an imaginary 
restaurant which offers the users to reserve tables over the internet. 

The "Facility" in "Facility Directory" really doesn't mean you can only 
enter rooms and the like. No, it's not the perfect name.

Anywho, on the "Add Facility Directory" form enter the following:

    Name: **Milliways**
    Subtitle: **The Restuarant at the End of the Universe**

    1st Category Name: **Window-Seat**
    2nd Category Name: **Smoking-Area**

    Enable searching: No

And add the directory.

### Add the Facility Items

In the newly created directory, click on "Add new..." and choose
"Facility Directory Item".

Enter the following on the "Add Facility Directory Item" form:

    Name: **Table #1**
    Description: **This table offers a great view.**
    Window-Seat: **Yes**
    Smoking-Area: **No**

Reapeat the same with the following data:

    Name: **Table #2**
    Description: **This table has a smoky atmosphere.**
    Window-Seat: **Yes**
    Smoking-Area: **Yes**

### Add a Resource

Click on Table #1 to get to its detail view. There click on "Add new..." again
and choose "Resource Item".

Enter the following:

    Name: **Dinner Reservation**
    First hour of the day: 17
    Last hour of the day: 22

Save the resource.



FAQ
---

 * Why is *Database X* not an option? / Why does Postgresql < 9.1 not work?

 seantis.reservation relies on a Postgresql feature introduced in 9.1 called
 "Serialized Transactions". Serialized transactions are transactions that, run on
 multiuser systems, are guaranteed to behave like they are run on a singleuser
 system.

 In other words, serialized transactions make it much easier to ensure that
 the data stays sane even when multiple write transactions are run concurrently.

 Other databases, like Oracle, also support this feature and it would be 
 possible to support those databases as well. Patches welcome.

Credits
-------

This project uses Silk Icons under Creative Commons 3.0.
Those icons were developed by http://www.famfamfam.com/lab/icons/silk/