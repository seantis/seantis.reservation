Seantis Reservation
===================

Plone addon to reserve stuff in a calendar.

Not a replacement for Outlook or Google Calendar, but a system to manage 
reservations on the backend and to provide them on the frontend.

Introduction
------------

Originally developed together with the municipality of Zug, Switzerland
this Addon aims to combine differing reservation systems into one
flexible solution.

It does so by providing a way to deal with the following usecases:

-  Manage meeting rooms in a company. Users reserve the rooms themselves
   without an authority confirming/denying their reservations.

-  Manage nursery spots. Parents apply for a spot in the nursery for
   their kid. Someone at the nursery goes through the applicants and
   decides who gets the spot. Parents may add an application to the
   waitinglist.

-  Manage community facilities. Citizens see the availability of
   facilities online and call the municipality to reserve a facility.
   The management is done internally (maybe through an already existing
   software). The addon is only used for display.

Screenshots
-----------

|overview example| |calendar example| |reserve example| |confirm
example|

Build Status
------------

|Build Status|

Latest PyPI Release
-------------------

|PyPI Release|

Requirements
------------

-  Python 2.7
-  Plone 4.3+ ( Plone 4.1 and 4.2 had to be dropped, sorry )
-  Linux / Posix ( Windows may or may not work )
-  Postgresql 9.1+ ( Older versions DO NOT work! )
-  1024MB+ RAM

seantis.reservation is tested using IE8+, Chrome, Firefox. IE7 is not
supported! Note also that IE8 and IE9 only work right if the Plone site
is in production mode. The reason for it is that those browsers ignore
every stylesheet after the 32th. In production these stylesheets are
merged.

Note that we also rely heavily on javascript as the calendar shown for
reservations is rendered through javascript. If your requirement is to run
without javascript then this is not the droid you are looking for.

Limitations
-----------

These are the things seantis.reservation currently doesn't do, or doesn't do
well:

-  Multilanguage. It is perfectly fine to run seantis.reservation in the language
   of your choice, though you might have to do some translations for yourself. However,
   you might find the ability to run the site in multiple languages (where the language
   is set on a per-request basis) to be lacking or with rough edges. It should mostly
   work but we cannot guarantee it or tell you that we tested this well.

-  Timezones. We currently do not store a timezone with the resource. Therefore
   comparing different resources of different timezones is a no go.

-  Recurrence. Though it is possible to create reservations with simple daily
   recurrence, it is not possible to modify them, so if you create 1000 recurrences
   and you make a mistake you have to delete all or adjust them each.

Installation
------------

The setup instructions assume an Ubuntu / Debian Server installation as
well as basic knowledge of Plone.

Install required packages
-------------------------

::

    sudo apt-get install git-core
    sudo apt-get install libxml2 libxml2-dev
    sudo apt-get install libxslt1.1 libxslt1-dev
    sudo apt-get install python2.7 python2.7-dev

Install Postgresql
------------------

Run the installer ::

    sudo apt-get install postgresql-9.1
    sudo apt-get install postgresql-9.1-dev

If the dev package cannot be found try ::

    sudo apt-get install postgresql-server-dev-all

Create a database user (replace ``your_password`` with your own). This
password is needed later! ::

    sudo -u postgres psql -c "CREATE USER reservation WITH PASSWORD 'your_password'"

Create the reservations database ::

    sudo -u postgres psql -c "CREATE DATABASE reservations ENCODING 'UTF8' TEMPLATE template0"

Grant the required privileges to the reservation user ::

    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE reservations to reservation"

Install Plone
-------------

Download the buildout configs to the folder which will hold your Plone
installation. ::

    wget -qO - https://raw.github.com/seantis/seantis.reservation/master/buildout/buildouts.sh | bash

Or if you don't have wget (like on OSX): ::

    curl https://raw.github.com/seantis/seantis.reservation/master/buildout/buildouts.sh | bash 

Edit your database connection settings in the database.cfg file. ::

    nano database.cfg

Download the boostrap script ::

    wget http://downloads.buildout.org/1/bootstrap.py

Again, alternatively with curl ::

    curl http://downloads.buildout.org/1/bootstrap.py > bootstrap.py

Bootstrap your environment ::

    python2.7 bootstrap.py

Run the installation (and get that coffee machine cracking) ::

    bin/buildout

If everything went well you may now start your instance ::

    bin/instance fg

Running Tests
-------------

The tests are run against a Postgres Database. This should be a database
used for this purpose only. Therefore you should first create said database ::

    sudo -u postgres psql -c "CREATE USER test WITH PASSWORD 'test'"

Create the test database ::

    sudo -u postgres psql -c "CREATE DATABASE test ENCODING 'UTF8' TEMPLATE template0"

Grant the required privileges to the test user ::

    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE test to test"

To get the test script you should run the development buildout ::

    bin/buildout -c develop.cfg

After that you need to tell the test script which database to use ::

    cd src/seantis.reservation/seantis/reservation
    cp test_database.py.example test_database.py

You tell it by editing test_database.py and adding a testdsn like this ::

    testdsn = "postgresql+psycopg2://test:test@localhost:5432/test"

You may then run the tests as follows ::

    bin/test -s seantis.reservation

Creating a Reservation Plone Site
---------------------------------

Create the Site
~~~~~~~~~~~~~~~

Having started your instance, navigate to the plone root: ::

    http://localhost:8080

It should say 'Plone is up and running'. On this site click "Create new
Plone site" If you used the develop.cfg the username and password are
"admin" and "admin".

Obviously you do not want to use develop.cfg in production!

On the "Create a Plone site" form, you should enter name and title of
your plone site, followed by checking the box of the following
Add-On:

**Seantis Reservation - for default plone theme**

Having done that, click "Create Plone Site"

Create Resource Folder
~~~~~~~~~~~~~~~~~~~~~~

On your freshly minted Plone Site, click on "Add new..." and choose
"Folder". Use any name you like.

Add a Resource
~~~~~~~~~~~~~~

In the newly created folder, click on "Display" and choose 
"Resource Listing".

This will turn the folder into a view designed for displaying Resources.

After changing the view click on "Add new..." and choose "Resource".
Enter any name you like.

You should now see a calendar in which you can create allocations that may
be reserved. One level up, in the folder view, you may add more resources and
compare them. Of course there is more to learn, but this is the basic setup of
the Seantis Reservation module.

Data Structure
--------------

To really understand seantis.reservation it is important to understand a
few core concepts:

Resource
~~~~~~~~

Resources are Dxterity content types who display a calendar and interact
with the core of seantis.reservation. They are heavy on the UI side of
things, while being nothing more than a foreign key in the database.

Allocations
~~~~~~~~~~~

Everyone familiar with Outlook or Google Calendar knows that one can
just click on an empty spot and add a new reservation.

In seantis.reservation this is not the case. In this module, a spot that
may be reserved must be marked as such first. This is called an
allocation.

The idea is to allocate time which may be reserved. It is like declaring
time that should be managed by reservations. Outlook and Google Calendar
implicitly see all time as allocated and under their management.

One reason for this is the fact that only through limiting the available
time we can calculate meaningful utilization numbers. Another reason is
that some periods of time may be overbooked, other times may not, or
generally speaking: some timeperiods are different than others.

Allocations therefore define how periods of time may be reserved. They
may not overlap for any given resource and they are independent of Plone
and part of the SQL database model.

Reserved Slots
~~~~~~~~~~~~~~

When reserving an allocation or a part of an allocation, reserved slots
are generated. They ensure that no reservation is ever granted twice by
accident.

Reserved slots may start every 5 minutes. At 5.35 or 5.40 for example,
but not at 5.36 or 5.39. When reserving 45 minutes of an allocation,
many reserved slots are spawned and aligned. Their primary keys then
ensure on a low level basis that no overlaps occur.

For a much needed example:

::

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

Of course there are a number of optimizations to ensure that we don't
generated millions of reserved slots. But this is basically it.

Reservations
~~~~~~~~~~~~

Reservations exist in two states: Pending and Approved.

Pending reservations are reservations on a waitinglist. Users have
submitted them, but nobody has confirmed them. They have therefore no
reserved slot associated with them.

Approved reservations are reservations who are associated with reserved
slots and are therefore confirmed and binding.

Note that it is possible in the UI side of seantis.reservation to go
from pending to confirmed automatically. This is called auto-approval.

FAQ
---

Why is *Database X* not an option? / Why does Postgresql < 9.1 not work?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

seantis.reservation relies on a Postgresql feature introduced in 9.1
called "Serialized Transactions". Serialized transactions are
transactions that, run on multiuser systems, are guaranteed to behave
like they are run on a singleuser system.

In other words, serialized transactions make it much easier to ensure
that the data stays sane even when multiple write transactions are run
concurrently.

Other databases, like Oracle, also support this feature and it would be
possible to support those databases as well. Patches welcome.

Note that MySQL has serialized transactions with InnoDB, but the
documentation does not make any clear guarantees and there is a debate
going on:

http://stackoverflow.com/questions/6269471/does-mysql-innodb-implement-true-serializable-isolation

Why did you choose SQL anyway? Why not use the ZODB? Why not *insert your favorite NoSQL DB here*?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  If a reservation is granted to you, noone else must get the same
   grant. Primary keys and transactions are a natural fit to ensure
   that.

-  Our data model is heavily structured and needs to be validated
   against a schema.

-  All clients must have the same data at all time. Not just eventually.

-  Complicated queries must be easy to develop as reporting matters.

-  The core of seantis.reservation should eventually be independent of
   Zope/Plone.

Why / How is my allocation colored? My allocation is green, but it should be orange/red!
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Basically colors are assigned to events based on their availability:

75-100% : Green / Available

1-74% : Orange / Partly Available

0% : Unavailable

The availability is calculated by taking the total time available and
dividing it by the time reserved. If an allocation is set to be approved
automatically (the default) a 0% availability also means that no new
reservations can be made.

If an allcation is set to be approved manually, there's automatically an
unlimited waitinglist. Reservations to that waitinglist can be made at
any time - unless the allocation setting is changed - and the number of
people in the waitinglist is shown on the allcation itself.

.. |overview example| image:: https://github.com/seantis/seantis.reservation/raw/master/screenshots/milliways-overview.png
.. |calendar example| image:: https://github.com/seantis/seantis.reservation/raw/master/screenshots/milliways-calendar.png
.. |reserve example| image:: https://github.com/seantis/seantis.reservation/raw/master/screenshots/milliways-reserve.png
.. |confirm example| image:: https://github.com/seantis/seantis.reservation/raw/master/screenshots/milliways-confirm.png
.. |Build Status| image:: https://secure.travis-ci.org/seantis/seantis.reservation.png
   :target: http://travis-ci.org/seantis/seantis.reservation
.. |PyPI Release| image:: https://pypip.in/v/seantis.dir.base/badge.png
    :target: https://crate.io/packages/seantis.dir.base
    :alt: Latest PyPI version