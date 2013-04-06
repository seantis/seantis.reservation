**THIS README IS A WORK IN PROGRESS**

seantis.reservation
===================

Plone addon to reserve stuff in a calendar.

![overview example](https://github.com/seantis/seantis.reservation/raw/master/screenshots/milliways-overview.png)
![calendar example](https://github.com/seantis/seantis.reservation/raw/master/screenshots/milliways-calendar.png)
![reserve example](https://github.com/seantis/seantis.reservation/raw/master/screenshots/milliways-reserve.png)
![confirm example](https://github.com/seantis/seantis.reservation/raw/master/screenshots/milliways-confirm.png)

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
   is only used for display.

Build Status
------------

[![Build Status](https://secure.travis-ci.org/seantis/seantis.reservation.png)](http://travis-ci.org/seantis/seantis.reservation)

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


Data Structure
--------------

To really understand seantis.reservation it is important to understand a few core concepts:

## Resource

Resources are Dxterity content types who display a calendar and interact with the core of seantis.reservation. They are heavy on the UI side of things, while being nothing more than a foreign key in the database. 

## Allocations

Everyone familiar with Outlook or Google Calendar knows that one can just click on an empty spot and add a new reservation.

In seantis.reservation this is not the case. In this module, a spot that may be reserved must be marked as such first. This is called an allocation.

The idea is to allocate time which may be reserved. It is like declaring time that should be managed by reservations. Outlook and Google Calendar implicitly see all time as allocated and under their management.

One reason for this is the fact that only through limiting the available time we can calculate meaningful utilization numbers. Another reason is that some periods of time may be overbooked, other times may not, or generally speaking: some timeperiods are different than others.

Allocations therefore define how periods of time may be reserved. They may not overlap for any given resource and they are independent of Plone and part of the SQL database model.

## Reserved Slots

When reserving an allocation or a part of an allocation, reserved slots are generated. They ensure that no reservation is ever granted twice by accident.

Reserved slots may start every 5 minutes. At 5.35 or 5.40 for example, but not at 5.36 or 5.39. When reserving 45 minutes of an allocation, many reserved slots are spawned and aligned. Their primary keys then ensure on a low level basis that no overlaps occur.

For a much needed example:

    Resource: 1234
    Allocation: 09:00 - 10:00

    => reserve 1234, 09:30 - 10:00

    Reserved Slots:
        1234 09:30
        1234 09:35
        1234 09:40
        1234 09:45
        1234 09:50
        1234 09:55

    => try to reserve 1234, 09:30 - 10:00 again

    Reserved Slot 1234, 09:30 already exists

Of course there are a number of optimizations to ensure that we don't generated millions of reserved slots. But this is basically it.

## Reservations

Reservations exist in two states: Pending and Approved.

Pending reservations are reservations on a waitinglist. Users have submitted them, but nobody has confirmed them. They have therefore no reserved slot associated with them.

Apporved reservations are reservations who are associated with reserved slots and are therefore confirmed and binding.

Note that it is possible in the UI side of seantis.reservation to go from pending to confirmed automatically. This is called auto-approval.

FAQ
---

### Why is *Database X* not an option? / Why does Postgresql < 9.1 not work?

seantis.reservation relies on a Postgresql feature introduced in 9.1 called
"Serialized Transactions". Serialized transactions are transactions that, run on
multiuser systems, are guaranteed to behave like they are run on a singleuser
system.

In other words, serialized transactions make it much easier to ensure that
the data stays sane even when multiple write transactions are run concurrently.

Other databases, like Oracle, also support this feature and it would be 
possible to support those databases as well. Patches welcome.

Note that MySQL has serialized transactions with InnoDB, but the documentation does not make any clear guarantees and there is a debate going on:

http://stackoverflow.com/questions/6269471/does-mysql-innodb-implement-true-serializable-isolation

### Why did you choose SQL anyway? Why not use the ZODB? Why not *insert your favorite NoSQL DB here*?
 
 * If a reservation is granted to you, noone else must get the same grant. 
  Primary keys and transactions are a natural fit to ensure that.

 * Our data model is heavily structured and needs to be validated against a schema.

 * All clients must have the same data at all time. Not just eventually.

 * Complicated queries must be easy to develop as reporting matters.

 * The core of seantis.reservation should eventually be independent of Zope/Plone.

### Why / How is my event colored? My event is green, but it should be orange/red!

Basically colors are assigned to events based on their availability:

75-100%
: Green / Available

1-74%
: Orange / Partly Available

0%
: Unavailable

Now what is meant by *availability*? You would think it's just the free hours divided by the total hours. In the simplest case that is actually true. Observe a partly available allocation without a quota:

    Allocation  08:00 - 10:00
    Reservation 08:00 - 09:00

    => 50% available

See `seantis.reservation.models.allocation.availability`

If we introduce allocation quotas, the picture gets more complicated. Observe a partly available allocation with a quota of 2:

    Allocation  08:00 - 10:00, Quota 2
    Reservation 08:00 - 09:00

    => 75% available

The allocation timespan may be reserved twice or 200%. 50% of one timespan is used. So 150% is free. 

Technically there are two allocations, one for each quota. We only show one and are interested in a number between 0 and 100, so we divide by two: 150% / 2 => 75%.

See `seantis.reseravtion.db.availability_by_allocations`

Still easy. Let's introduce a waitinglist. Doing so gives us a completely new availability. The waitinglist availability. Observe:

    Waitinglist Spots: 100
    Reservations in the Waitinglist: 10

    => waitinglist 90% available

This waitinglist availability puts us between a rock and a hard place:

 - If a reservation is fully booked (0% available), but the waitinglist is 100% open, do we show the allocation as unavailable? 

 - What about a free resource whose waitinglist is full? Do we really show an event as available if nobody can submit a reservation because the waitinglist is full?

We decided to do something in the middle. We will show the average of allocation and waitinglist. 

UNLESS the the waitinglist is full. If the waitinglist is full the user cannot possibly submit a reservation and we really want to be sure that we show unavailable when the allocation is exactly that.

We could accomodate everyone (and make nobody happy), by doing the following:

    Allocation  08:00 - 10:00

    => 100% free

    Waitinglist Spots: 3
    Reservations in the Waitinglist: 3

    => 100% free

    (0% + 100%) / 2

    => 50% free

But we want to let the user know that as long as an event is not unavailable he might have a chance to reserve it (somebody might of course always be faster).

See `seantis.reservation.utils.event_avilablity`

**tl;dr**
Your event is unavailable if you cannot submit a reservation to it. It is shown as partly available if availability is or waitinglist spots are dwindling. It is shown as available if all is good.

Credits
-------

This project uses Silk Icons under Creative Commons 3.0.
Those icons were developed by http://www.famfamfam.com/lab/icons/silk/