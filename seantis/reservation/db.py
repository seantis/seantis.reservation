from logging import getLogger
log = getLogger('seantis.reservation')

from uuid import UUID
from uuid import uuid1 as new_uuid
from datetime import datetime, timedelta, MINYEAR, MAXYEAR
from itertools import groupby

from zope.event import notify

from sqlalchemy.sql import and_, or_, not_
from sqlalchemy.orm import joinedload, exc
from sqlalchemy import func, null

from seantis.reservation.events import (
    ReservationsMadeEvent,
    ReservationsApprovedEvent,
    ReservationsDeniedEvent,
    ReservationsRevokedEvent,
    ReservationsConfirmedEvent,
    ReservationTimeChangedEvent
)

from seantis.reservation.models import (
    Allocation, ReservedSlot, Reservation
)
from seantis.reservation.error import (
    AffectedPendingReservationError,
    AffectedReservationError,
    AlreadyReservedError,
    InvalidAllocationError,
    InvalidQuota,
    InvalidReservationError,
    InvalidReservationToken,
    NoReservationsToConfirm,
    NotReservableError,
    OverlappingAllocationError,
    QuotaImpossible,
    QuotaOverLimit,
    ReservationParametersInvalid,
    ReservationTooLong,
    TimerangeTooLong,
)

from seantis.plonetools.schemafields import validate_email

from seantis.reservation.session import serialized
from seantis.reservation.raster import rasterize_span, MIN_RASTER_VALUE
from seantis.reservation import utils
from seantis.reservation import Session


def all_allocations_in_range(start, end):
    # Query version of utils.overlaps
    return Session.query(Allocation).filter(
        or_(
            and_(
                Allocation._start <= start,
                start <= Allocation._end
            ),
            and_(
                start <= Allocation._start,
                Allocation._start <= end
            )
        )
    )


def availability_by_allocations(allocations):
    """Takes any iterator with alloctions and calculates the availability.
    Counts missing mirrors as 100% free and returns a value between 0-100 in
    any case.
    For single allocations check the allocation.availability property.

    """
    total, expected_count, count = 0, 0, 0
    for allocation in allocations:
        total += allocation.availability
        count += 1

        # Sum up the expected number of allocations. Missing allocations
        # indicate mirrors that have not yet been physically created.
        if allocation.is_master:
            expected_count += allocation.quota

    if not expected_count:
        return 0

    missing = expected_count - count
    total += missing * 100

    return total / expected_count


def availability_by_range(start, end, resources, is_exposed):
    """Returns the availability for the given resources in the given range.
    The callback *is_exposed* is used to check if the allocation is visible
    to the current user. This should usually be the exposure.for_allocations
    return value.

    """

    query = all_allocations_in_range(start, end)
    query = query.filter(Allocation.mirror_of.in_(resources))
    query = query.options(joinedload(Allocation.reserved_slots))

    allocations = (a for a in query if is_exposed(a))
    return availability_by_allocations(allocations)


def availability_by_day(start, end, resources, is_exposed):
    """Availability by range with a twist. Instead of returning a grand total,
    a dictionary is returned with each day in the range as key and a tuple of
    availability and the resources counted for that day.

    WARNING, this function should run as linearly as possible as a lot
    of records might be processed.

    """
    query = all_allocations_in_range(start, end)
    query = query.filter(Allocation.mirror_of.in_(resources))
    query = query.options(joinedload(Allocation.reserved_slots))
    query = query.order_by(Allocation._start)

    group = groupby(query, key=lambda a: a._start.date())
    days = {}

    for day, allocations in group:

        exposed = []
        members = set()

        for a in (a for a in allocations if is_exposed(a)):
            members.add(a.mirror_of)
            exposed.append(a)

        if not exposed:
            continue

        total = availability_by_allocations(exposed)

        days[day] = (total, members)

    return days


def reservations_by_session(session_id):

    # be sure to not query for all reservations. since a query should be
    # returned in any case we just use an impossible clause

    # this is mainly a security feature
    if not session_id:
        log.warn('Empty session id')
        return Session.query(Reservation).filter("0=1")

    query = Session.query(Reservation)
    query = query.filter(Reservation.session_id == session_id)
    query = query.order_by(Reservation.created)

    return query


@serialized
def confirm_reservations_for_session(session_id, token=None, language=None):
    """ Confirms all reservations of the given session id. Optionally
    confirms only the reservations with the given token. All if None.

    The langauge given is the language used for the confirmation event (which
    leads to an email sent in this language). Default is the site language.

    """

    assert session_id

    if not language:
        language = utils.get_current_site_language()

    reservations = reservations_by_session(session_id)

    if token:
        reservations = reservations.filter(Reservation.token == token)

    reservations = reservations.all()

    if not reservations:
        raise NoReservationsToConfirm

    for reservation in reservations:
        reservation.session_id = None

    notify(ReservationsConfirmedEvent(reservations, language))


@serialized
def remove_reservations_from_session(session_id, token):
    """ Removes the reservations with the given session_id and token. """

    assert token and session_id

    reservations = reservations_by_session(session_id)
    reservations = reservations.filter(Reservation.token == token)
    reservations = reservations.order_by(False)

    reservations.delete('fetch')

    # if we get here the token must be valid, we should then check if the
    # token is used in the reserved slots, because with autoapproval these
    # slots may be created straight away.

    slots = Session.query(ReservedSlot).filter(
        ReservedSlot.reservation_token == token
    )

    slots.delete('fetch')

    # we also update the timestamp of existing reservations within
    # the same session to ensure that we account for the user's activity
    # properly during the session expiration cronjob. Otherwise it is
    # possible that a user removes the latest reservations only to see
    # the rest of them vanish because his older reservations were
    # already old enough to be counted as expired.

    query = Session.query(Reservation)
    query = query.filter(Reservation.session_id == session_id)

    query.update({"modified": utils.utcnow()})


def find_expired_reservation_sessions(expiration_date):
    """ Goes through all reservations and returns the session ids of the
    unconfirmed ones which are older than the given expiration date.
    By default the expiration date is now - 15 minutes.

    Note that this method goes through ALL RESERVATIONS OF THE DATABASE. If
    this is not desired have a look at buildout/database.cfg.example to
    setup each site with its own database.

    """

    expiration_date = expiration_date or (
        utils.utcnow() - timedelta(minutes=15)
    )

    # first get the session ids which are expired
    query = Session.query(
        Reservation.session_id,
        func.max(Reservation.created),
        func.max(Reservation.modified)
    )

    query = query.group_by(Reservation.session_id)

    # != null() because != None is not allowed by PEP8
    query = query.filter(Reservation.session_id != null())

    # the idea is to remove all reservations belonging to sessions whose
    # latest update is expired - either delete the whole session or let
    # all of it be
    expired_sessions = []

    for session_id, created, modified in query.all():

        modified = modified or created
        assert created and modified

        if max(created, modified) < expiration_date:
            expired_sessions.append(session_id)

    return expired_sessions


@serialized
def remove_expired_reservation_sessions(expiration_date=None):
    """ Removes all reservations from all databases which have an
    expired session_id.

    Since this only concerns 'old' sessions it shouldn't be a problem
    however.

    """

    expired_sessions = find_expired_reservation_sessions(expiration_date)

    # remove those session ids
    if expired_sessions:
        reservations = Session.query(Reservation)
        reservations = reservations.filter(
            Reservation.session_id.in_(expired_sessions)
        )

        slots = Session.query(ReservedSlot)
        slots = slots.filter(
            ReservedSlot.reservation_token.in_(
                reservations.with_entities(Reservation.token).subquery()
            )
        )

        slots.delete('fetch')
        reservations.delete('fetch')

    return expired_sessions


@serialized
def extinguish_resource(resource_uuid):
    """ WARNING:
    Completely removes any trace of the given resource uuid. That means
    all reservations, reserved slots and allocations!

    """

    # set the language as this may be called when deleting plone which
    # will render all plone utils calls, like portal_languages, useless
    scheduler = Scheduler(resource_uuid, language='en')
    scheduler.managed_reservations().delete('fetch')
    scheduler.managed_reserved_slots().delete('fetch')
    scheduler.managed_allocations().delete('fetch')


class Scheduler(object):
    """Used to manage a resource as well as all connected mirrors.

    Master -> Mirror relationship
    =============================

    Mirrors are viewed as resources which mirror a master resource. These
    mirrors do not really exist as seantis.reservation.resource types in plone
    (unlike the master). Instead they have their own resource uuids which are
    calculated by creating new uuids from the master's uuid and the number of
    the mirror (see utils.generate_uuids).

    The reason for this mechanism is to ensure two things:

    - No more mirrors than required are created (if we tried that we would get
      integrity errors as the resource plus the start-time are unique)

    - The reservation slot does not need to carry any information about the
      mirror. It just references a resource uuid

    Since we do not want to calculate these mirror uuids all the time, since it
    is a somewhat expensive calculations and because it is a bit of hassle, we
    store the master uuid in the mirror_of field of each allocation record.

    """

    def __init__(self, resource_uuid, is_exposed=None, language=None):

        try:
            self.uuid = UUID(resource_uuid)
        except AttributeError:
            self.uuid = resource_uuid

        self.is_exposed = is_exposed or (lambda allocation: True)

        # the language is used for the events that are being sent
        # if no language is given, then the current site language is used
        if language:
            self.language = language
        else:
            self.language = utils.get_current_site_language()

    # using the managed_* functions as a starting point for queries is a good
    # idea because the querie's scope will always be correctly limited

    def managed_reservations(self):
        """ The reservations managed by this scheduler / resource. """
        query = Session.query(Reservation)
        query = query.filter(Reservation.resource == self.uuid)

        return query

    def managed_allocations(self):
        """ The allocations managed by this scheduler / resource. """
        query = Session.query(Allocation)
        query = query.filter(Allocation.mirror_of == self.uuid)

        return query

    def managed_reserved_slots(self):
        """ The reserved_slots managed by this scheduler / resource. """
        uuids = self.managed_allocations().with_entities(Allocation.resource)

        query = Session.query(ReservedSlot)
        query = query.filter(ReservedSlot.resource.in_(uuids))

        return query

    @serialized
    def allocate(self, dates, raster=15, quota=None, partly_available=False,
                 grouped=False, approve_manually=True,
                 reservation_quota_limit=0, whole_day=False
                 ):
        """Allocates a spot in the calendar.

        An allocation defines a timerange which can be reserved. No
        reservations can exist outside of existing allocations. In fact any
        reserved slot will link to an allocation.

        An allocation may be available as a whole (to reserve all or nothing).
        It may also be partly available which means reservations can be made
        for parts of the allocation.

        If an allocation is partly available a raster defines the granularity
        with which a reservation can be made (e.g. a raster of 15min will
        ensure that reservations are at least 15 minutes long and start either
        at :00, :15, :30 or :45)

        The reason for the raster is mainly to ensure that different
        reservations trying to reserve overlapping times need the same keys in
        the reserved_slots table, ensuring integrity at the database level.

        Allocations may have a quota, which determines how many times an
        allocation may be reserved. Quotas are enabled using a master-mirrors
        relationship.

        The master is the first allocation to be created. The mirrors copies of
        that allocation. See Scheduler.__doc__

        """
        dates = utils.pairs(dates)

        group = new_uuid()
        quota = quota or 1

        # if the allocation is not partly available the raster is set to lowest
        # possible raster value
        raster = partly_available and raster or MIN_RASTER_VALUE

        # the whole day option results in the dates being aligned to
        # the beginning of the day / end of it -> not timezone aware!
        if whole_day:
            for ix, (start, end) in enumerate(dates):
                dates[ix] = utils.align_range_to_day(start, end)

        # Ensure that the list of dates contains no overlaps inside
        for start, end in dates:
            if utils.count_overlaps(dates, start, end) > 1:
                raise InvalidAllocationError

        # Make sure that this span does not overlap another master
        for start, end in dates:
            start, end = rasterize_span(start, end, raster)

            existing = self.allocations_in_range(start, end).first()
            if existing:
                raise OverlappingAllocationError(start, end, existing)

        # Write the master allocations
        allocations = []
        for start, end in dates:
            allocation = Allocation(raster=raster)
            allocation.start = start
            allocation.end = end
            allocation.resource = self.uuid
            allocation.quota = quota
            allocation.mirror_of = self.uuid
            allocation.partly_available = partly_available
            allocation.approve_manually = approve_manually
            allocation.reservation_quota_limit = reservation_quota_limit

            if grouped:
                allocation.group = group
            else:
                allocation.group = new_uuid()

            allocations.append(allocation)

        Session.add_all(allocations)

        return allocations

    @serialized
    def change_quota(self, master, new_quota):
        """ Changes the quota of a master allocation.

        Fails if the quota is already exhausted.

        When the quota is decreased a reorganization of the mirrors is
        triggered. Reorganizing means eliminating gaps in the chain of mirrors
        that emerge when reservations are removed:

        Initial State:
        1   (master)    Free
        2   (mirror)    Free
        3   (mirror)    Free

        Reservations are made:
        1   (master)    Reserved
        2   (mirror)    Reserved
        3   (mirror)    Reserved

        A reservation is deleted:
        1   (master)    Reserved
        2   (mirror)    Free     <-- !!
        3   (mirror)    Reserved

        Reorganization is performed:
        1   (master)    Reserved
        2   (mirror)    Reserved <-- !!
        3   (mirror)    Free     <-- !!

        The quota is decreased:
        1   (master)    Reserved
        2   (mirror)    Reserved

        In other words, the reserved allocations are moved to the beginning,
        the free allocations moved at the end. This is done to ensure that
        the sequence of generated uuids for the mirrors always represent all
        possible keys.

        Without the reorganization we would see the following after
        decreasing the quota:

        The quota is decreased:
        1   (master)    Reserved
        3   (mirror)    Reserved

        This would make it impossible to calculate the mirror keys. Instead the
        existing keys would have to queried from the database.

        """

        assert new_quota > 0, "Quota must be greater than 0"

        if new_quota == master.quota:
            return

        if new_quota > master.quota:
            master.quota = new_quota
            return

        # Make sure that the quota can be decreased
        mirrors = self.allocation_mirrors_by_master(master)
        allocations = [master] + mirrors

        free_allocations = [a for a in allocations if a.is_available()]

        required = master.quota - new_quota
        if len(free_allocations) < required:
            raise AffectedReservationError(None)

        # get a map pointing from the existing uuid to the newly assigned uuid
        reordered = self.reordered_keylist(allocations, new_quota)

        # unused keys are the ones not present in the newly assignd uuid list
        unused = set(reordered.keys()) - set(reordered.values()) - set((None,))

        # get a map for resource_uuid -> allocation.id
        ids = dict(((a.resource, a.id) for a in allocations))

        for allocation in allocations:

            # change the quota for all allocations
            allocation.quota = new_quota

            # the value is None if the allocation is not mapped to a new uuid
            new_resource = reordered[allocation.resource]
            if not new_resource:
                continue

            # move all slots to the mapped allocation id
            new_id = ids[new_resource]

            for slot in allocation.reserved_slots:
                # build a query here as the manipulation of mapped objects in
                # combination with the delete query below seems a bit
                # unpredictable given the cascading of changes

                query = Session.query(ReservedSlot)
                query = query.filter(and_(
                    ReservedSlot.resource == slot.resource,
                    ReservedSlot.allocation_id == slot.allocation_id,
                    ReservedSlot.start == slot.start
                ))
                query.update(
                    {
                        ReservedSlot.resource: new_resource,
                        ReservedSlot.allocation_id: new_id
                    }
                )

        # get rid of the unused allocations (always preserving the master)
        if unused:
            query = Session.query(Allocation)
            query = query.filter(Allocation.resource.in_(unused))
            query = query.filter(Allocation.id != master.id)
            query = query.filter(Allocation._start == master._start)
            query.delete('fetch')

    def reordered_keylist(self, allocations, new_quota):
        """ Creates the map for the keylist reorganzation.

        Each key of the returned dictionary is a resource uuid pointing to the
        resource uuid it should be moved to. If the allocation should not be
        moved they key-value is None.

        """
        masters = [a for a in allocations if a.is_master]
        assert(len(masters) == 1)

        master = masters[0]
        allocations = dict(((a.resource, a) for a in allocations))

        # generate the keylist (the allocation resources may be unordered)
        keylist = [master.resource]
        keylist.extend(utils.generate_uuids(master.resource, master.quota))

        # prefill the map
        reordered = dict(((k, None) for k in keylist))

        # each free allocation increases the offset by which the next key
        # for a non-free allocation is acquired
        offset = 0
        for ix, key in enumerate(keylist):
            if allocations[key].is_available():
                offset += 1
            else:
                reordered[key] = keylist[ix - offset]

        return reordered

    def allocation_by_id(self, id):
        query = self.managed_allocations()
        query = query.filter(Allocation.mirror_of == self.uuid)
        query = query.filter(Allocation.id == id)
        return query.one()

    def allocations_by_ids(self, ids):
        query = self.managed_allocations()
        query = query.filter(Allocation.id.in_(ids))
        query = query.order_by(Allocation._start)
        return query

    def allocations_by_group(self, group, masters_only=True):
        return self.allocations_by_groups([group], masters_only=masters_only)

    def allocations_by_groups(self, groups, masters_only=True):
        query = self.managed_allocations()
        query = query.filter(Allocation.group.in_(groups))

        if masters_only:
            query = query.filter(Allocation.resource == self.uuid)

        return query

    def allocations_in_range(self, start, end, masters_only=True):
        query = self.managed_allocations()
        query = query.filter(
            or_(
                and_(
                    Allocation._start <= start,
                    start <= Allocation._end
                ),
                and_(
                    start <= Allocation._start,
                    Allocation._start <= end
                )
            )
        )

        if masters_only:
            query = query.filter(Allocation.resource == self.uuid)

        return query

    def allocations_by_reservation(self, token, id=None):
        """ Returns the allocations for the reservation if it was *approved*,
        pending reservations return nothing. If you need to get the allocation
        a pending reservation might be targeting, use _target_allocations
        in model.reservation.

        """

        # TODO -> this is much too joiny, it was easier when we assumed
        # that there would be one reservation per token, now that there
        # is more than one reservation per token we should denormalize
        # this a little by adding the reservation_id to the reserved slot

        groups = self.managed_reservations()
        groups = groups.with_entities(Reservation.target)
        groups = groups.filter(Reservation.token == token)

        if id is not None:
            groups = groups.filter(Reservation.id == id)

        allocations = self.managed_allocations()
        allocations = allocations.with_entities(Allocation.id)
        allocations = allocations.filter(Allocation.group.in_(
            groups.subquery()
        ))

        query = self.managed_allocations()
        query = query.join(ReservedSlot)
        query = query.filter(
            ReservedSlot.reservation_token == token
        )
        query = query.filter(
            ReservedSlot.allocation_id.in_(
                allocations.subquery()
            )
        )
        return query

    def allocation_by_date(self, start, end):
        query = self.allocations_in_range(start, end)
        return query.one()

    def allocation_mirrors_by_master(self, master):
        return [s for s in master.siblings() if not s.is_master]

    def dates_by_group(self, group):
        query = self.allocations_by_group(group)
        query = query.with_entities(Allocation._start, Allocation._end)

        return query.all()

    def dates_by_allocation_ids(self, ids, start_time=None, end_time=None):

        for allocation in self.allocations_by_ids(ids).all():

            s = start_time or allocation.display_start.time()
            e = end_time or allocation.display_end.time()

            s, e = allocation.limit_timespan(s, e)

            yield s, e - timedelta(microseconds=1)

    def manual_approval_required(self, ids):
        """ Returns True if any of the allocations require manual approval. """
        query = self.allocations_by_ids(ids)
        query = query.filter(Allocation.approve_manually == True)

        return query.first() and True or False

    def render_allocation(self, allocation):
        return self.is_exposed(allocation)

    def availability(self, start=None, end=None):
        """Goes through all allocations and sums up the availability."""

        if not (start and end):
            start = datetime(MINYEAR, 1, 1)
            end = datetime(MAXYEAR, 12, 31)

        return availability_by_range(start, end, [self.uuid], self.is_exposed)

    @serialized
    def move_allocation(
            self, master_id, new_start=None, new_end=None,
            group=None, new_quota=None, approve_manually=None,
            reservation_quota_limit=0, whole_day=None):

        assert master_id
        assert any([new_start and new_end, group, new_quota])

        # Find allocation
        master = self.allocation_by_id(master_id)
        mirrors = self.allocation_mirrors_by_master(master)
        changing = [master] + mirrors
        ids = [c.id for c in changing]

        assert(group or master.group)

        # Simulate the new allocation
        new_start = new_start or master.start
        new_end = new_end or master.end

        if whole_day:
            new_start, new_end = utils.align_range_to_day(new_start, new_end)

        new = Allocation(start=new_start, end=new_end, raster=master.raster)

        # Ensure that the new span does not overlap an existing one
        existing_allocations = self.allocations_in_range(new.start, new.end)

        for existing in existing_allocations:
            if existing.id not in ids:
                raise OverlappingAllocationError(new.start, new.end, existing)

        for change in changing:

            if change.partly_available:
                # confirmed reservations
                for reservation in change.reserved_slots:
                    if not new.contains(reservation.start, reservation.end):
                        raise AffectedReservationError(reservation)

                # pending reservations
                if change.is_master:  # (mirrors return the same values)
                    for pending in change.pending_reservations.with_entities(
                            Reservation.start, Reservation.end):
                        if not new.contains(*pending):
                            raise AffectedPendingReservationError(pending)

            else:
                # confirmed reservations
                if change.start != new.start or change.end != new.end:
                    if len(change.reserved_slots):
                        raise AffectedReservationError(
                            change.reserved_slots[0]
                        )

                    if change.is_master and \
                            change.pending_reservations.count():
                        raise AffectedPendingReservationError(
                            change.pending_reservations[0]
                        )

        # the following attributes must be equal over all group members
        # (this still allows to use move_allocation to remove an allocation
        #  from an existing group by specifiying the new group)
        for allocation in self.allocations_by_group(group or master.group):

            if approve_manually is not None:
                allocation.approve_manually = approve_manually

            if reservation_quota_limit is not None:
                allocation.reservation_quota_limit = reservation_quota_limit

            if new_quota is not None and allocation.is_master:
                self.change_quota(allocation, new_quota)

        for change in changing:
            change.start = new.start
            change.end = new.end
            change.group = group or master.group

    @serialized
    def remove_allocation(self, id=None, groups=None):
        if id:
            master = self.allocation_by_id(id)
            allocations = [master]
            allocations.extend(self.allocation_mirrors_by_master(master))
        elif groups:
            allocations = self.allocations_by_groups(
                groups, masters_only=False
            )
        else:
            raise NotImplementedError

        for allocation in allocations:
            assert allocation.mirror_of == self.uuid, """
                Trying to delete an allocation from a different resource than
                the scheduler and context. This is a serious error or
                someone trying to something funny with the POST parameters.
            """

            if len(allocation.reserved_slots) > 0:
                raise AffectedReservationError(allocation.reserved_slots[0])

            if allocation.pending_reservations.count():
                raise AffectedPendingReservationError(
                    allocation.pending_reservations[0]
                )

        for allocation in allocations:
            if not allocation.is_transient:
                Session.delete(allocation)

    @serialized
    def reserve(self, email, dates=None, group=None, data=None,
                session_id=None, quota=1):
        """ First step of the reservation.

        Seantis.reservation uses a two-step reservation process. The first
        step is reserving what is either an open spot or a place on the
        waiting list.

        The second step is to actually write out the reserved slots, which
        is done by approving an existing reservation.

        Most checks are done in the reserve functions. The approval step
        only fails if there's no open spot.

        This function returns a reservation token which can be used to
        approve the reservation in approve_reservation.

        """

        assert (dates or group) and not (dates and group)

        validate_email(email)

        if group:
            dates = self.dates_by_group(group)

        dates = utils.pairs(dates)

        # First, the request is checked for saneness. If any requested
        # date cannot be reserved the request as a whole fails.
        for start, end in dates:

            # are the parameters valid?
            if abs((end - start).days) >= 1:
                raise ReservationTooLong

            if start > end or (end - start).seconds < 5 * 60:
                raise ReservationParametersInvalid

            # can all allocations be reserved?
            for allocation in self.allocations_in_range(start, end):

                # start and end are not rasterized, so we need this check
                if not allocation.overlaps(start, end):
                    continue

                assert allocation.is_master

                # with manual approval the reservation ends up on the
                # waitinglist and does not yet need a spot
                if not allocation.approve_manually:
                    if not self.find_spot(allocation, start, end):
                        raise AlreadyReservedError

                    free = self.free_allocations_count(allocation, start, end)
                    if free < quota:
                        raise AlreadyReservedError

                if allocation.reservation_quota_limit > 0:
                    if allocation.reservation_quota_limit < quota:
                        raise QuotaOverLimit

                if allocation.quota < quota:
                    raise QuotaImpossible

                if quota < 1:
                    raise InvalidQuota

        # ok, we're good to go
        token = new_uuid()
        reservations = []

        # groups are reserved by group-identifier - so all members of a group
        # or none of them. As such there's no start / end date which is defined
        # implicitly by the allocation
        def new_reservations_by_group(group):
            if group:
                reservation = Reservation()
                reservation.token = token
                reservation.target = group
                reservation.status = u'pending'
                reservation.target_type = u'group'
                reservation.resource = self.uuid
                reservation.data = data
                reservation.session_id = session_id
                reservation.email = email.strip()
                reservation.quota = quota

                yield reservation

        # all other reservations are reserved by start/end date
        def new_reservations_by_dates(dates):
            already_reserved_groups = set()

            for start, end in dates:
                for allocation in self.allocations_in_range(start, end):
                    if allocation.group in already_reserved_groups:
                        continue

                    if not allocation.overlaps(start, end):
                        continue

                    # automatically reserve the whole group if the allocation
                    # is part of a group
                    if allocation.in_group:
                        already_reserved_groups.add(allocation.group)

                        # I really want to use 'yield from'. Python 3 ftw!
                        for r in new_reservations_by_group(allocation.group):
                            yield r
                    else:
                        reservation = Reservation()
                        reservation.token = token
                        reservation.start, reservation.end = rasterize_span(
                            start, end, allocation.raster
                        )
                        reservation.target = allocation.group
                        reservation.status = u'pending'
                        reservation.target_type = u'allocation'
                        reservation.resource = self.uuid
                        reservation.data = data
                        reservation.session_id = session_id
                        reservation.email = email.strip()
                        reservation.quota = quota

                        yield reservation

        # create the reservations
        if group:
            reservations = tuple(new_reservations_by_group(group))
        else:
            reservations = tuple(new_reservations_by_dates(dates))

        if not reservations:
            raise InvalidReservationError

        for reservation in reservations:
            Session.add(reservation)

        notify(ReservationsMadeEvent(reservations, self.language))

        return token

    @serialized
    def _approve_reservation_record(self, reservation):
        # write out the slots
        slots_to_reserve = []

        if reservation.target_type == u'group':
            dates = self.dates_by_group(reservation.target)
        else:
            dates = ((reservation.start, reservation.end),)

        # the reservation quota is simply implemented by multiplying the
        # dates which are approved

        dates = dates * reservation.quota

        for start, end in dates:

            for allocation in self.reservation_targets(start, end):

                for slot_start, slot_end in \
                        allocation.all_slots(start, end):
                    slot = ReservedSlot()
                    slot.start = slot_start
                    slot.end = slot_end
                    slot.resource = allocation.resource
                    slot.reservation_token = reservation.token

                    # the slots are written with the allocation
                    allocation.reserved_slots.append(slot)
                    slots_to_reserve.append(slot)

                # the allocation may be a fake one, in which case we
                # must make it realz yo
                if allocation.is_transient:
                    Session.add(allocation)

        reservation.status = u'approved'

        if not slots_to_reserve:
            raise NotReservableError

        return slots_to_reserve

    @serialized
    def approve_reservations(self, token):
        """ This function approves an existing reservation and writes the
        reserved slots accordingly.

        Returns a list with the reserved slots.

        """

        slots_to_reserve = []

        reservations = self.reservations_by_token(token).all()

        for reservation in reservations:
            slots_to_reserve.extend(
                self._approve_reservation_record(reservation)
            )

        notify(ReservationsApprovedEvent(reservations, self.language))

        return slots_to_reserve

    @serialized
    def deny_reservation(self, token):
        """ Denies a pending reservation, removing it from the records and
        sending an email to the reservee.

        """

        query = self.reservations_by_token(token)
        query = query.filter(Reservation.status == u'pending')

        reservations = query.all()

        query.delete()

        notify(ReservationsDeniedEvent(reservations, self.language))

    @serialized
    def revoke_reservation(self, token, reason, id=None, send_email=True):
        """ Revoke a reservation and inform the user of that."""

        reason = reason or u''

        # sending the email first is no problem as it won't work if
        # an exception triggers later in the request
        reservations = self.reservations_by_token(token, id).all()

        notify(ReservationsRevokedEvent(
            reservations, self.language, reason, send_email
        ))

        self.remove_reservation(token, id)

    @serialized
    def remove_reservation(self, token, id=None):
        """ Removes all reserved slots of the given reservation token.

        Note that removing a reservation does not let the reservee know that
        his reservation has been removed.

        If you want to let the reservee know what happened,
        use revoke_reservation.

        The id is optional. If given, only the reservation with the given
        token AND id is removed.

        """

        slots = self.reserved_slots_by_reservation(token, id)

        for slot in slots:
            Session.delete(slot)

        self.reservations_by_token(token, id).delete('fetch')

    @serialized
    def change_email(self, token, new_email):
        for reservation in self.reservations_by_token(token).all():
            reservation.email = new_email

    @serialized
    def change_reservation_data(self, token, data):

        for reservation in self.reservations_by_token(token).all():
            reservation.data = data

    @serialized
    def change_reservation_time_candidates(self, tokens=None):
        """ Returns the reservations that fullfill the restrictions
        imposed by change_reservation_time.

        Pass a list of reservaiton tokens to further limit the results.

        """

        query = self.managed_reservations()
        query = query.filter(Reservation.status == 'approved')
        query = query.filter(Reservation.target_type == 'allocation')

        groups = self.managed_allocations().with_entities(Allocation.group)
        groups = groups.filter(Allocation.partly_available == True)

        query = query.filter(Reservation.target.in_(groups.subquery()))

        if tokens:
            query = query.filter(Reservation.token.in_(tokens))

        return query

    @serialized
    def change_reservation_time(
        self, token, id, new_start, new_end, send_email=True, reason=None
    ):
        """ Allows to change the timespan of a reservation under certain
        conditions:

        - The new timespan must be reservable inside the existing allocation.
          (So you cannot use this method to reserve another allocation)
        - The referenced allocation must not be in a group.
        - The referenced allocation must be partly available.
        - The referenced reservation must be approved

        There is really only one usecase that this function works for:

        The user wants to change the timespan of a reservation in a meeting
        room kind of setup where you have lots of partly-available
        allocations.

        Returns True if a change was made.

        Just like revoke_reservation, this function raises an event which
        includes a send_email flag and a reason which may be used to inform
        the user of the changes to his reservation.

        see seantis.reservation.interfaces.IReservationTimeChangedEvent

        """

        # check for the reservation first as the allocation won't exist
        # if the reservation has not been approved yet
        assert new_start and new_end

        existing_reservation = self.reservations_by_token(token, id).one()

        assert existing_reservation.status == 'approved', """
            Reservation must be approved.
        """

        # if there's nothing to change, do not change
        if existing_reservation.start == new_start:
            if existing_reservation.end == new_end:
                return False
            if existing_reservation.end == new_end - timedelta(microseconds=1):
                return False

        # will return raise a MultipleResultsFound exception if this is a group
        allocation = self.allocations_by_reservation(token, id).one()

        assert allocation.partly_available, """
            Allocation must be partly available.
        """

        if not allocation.contains(new_start, new_end):
            raise TimerangeTooLong()

        reservation_arguments = dict(
            email=existing_reservation.email,
            dates=(new_start, new_end),
            data=existing_reservation.data,
            quota=existing_reservation.quota
        )

        old_start = existing_reservation.display_start
        old_end = existing_reservation.display_end

        Session.begin_nested()

        try:
            self.remove_reservation(token, id)

            new_token = self.reserve(**reservation_arguments)
            new_reservation = self.reservations_by_token(new_token).one()
            new_reservation.id = id
            new_reservation.token = token

            self._approve_reservation_record(new_reservation)

            notify(ReservationTimeChangedEvent(
                reservation=new_reservation,
                language=self.language,
                old_time=(old_start, old_end),
                new_time=(new_start, new_end),
                send_email=send_email,
                reason=reason or u'',
            ))
        except:
            Session.rollback()
            raise
        else:
            Session.commit()

        return True

    def find_spot(self, master_allocation, start, end):
        """ Returns the first free allocation spot amongst the master and the
        mirrors. Honors the quota set on the master and will only try the
        master if the quota is set to 1.

        If no spot can be found, None is returned.

        """
        master = master_allocation
        if master.is_available(start, end):
            return master

        if master.quota == 1:
            return None

        mirrors = self.allocation_mirrors_by_master(master)
        tries = master.quota - 1

        for mirror in mirrors:
            if mirror.is_available(start, end):
                return mirror

            if tries >= 1:
                tries -= 1
            else:
                return None

    def search_allocations(
        self, start, end,
        days=None,
        minspots=0,
        available_only=False,
        whole_day='any',
        groups='any',
        strict=False
    ):
        """ Search allocations using a number of options. The date is split
        into date/time. All allocations between start and end date within
        the given time (on each day) are included.

        For example, start=01.01.2012 12:00 end=31.01.2012 14:00 will include
        all allocaitons in January 2012 which OVERLAP the given times. So an
        allocation starting at 11:00 and ending at 12:00 will be included!

        WARNING allocations not matching the start/end date may be included
        if they belong to a group from which a member *is* included!

        If that behavior is not wanted set 'strict' to True
        or set 'include_groups' to 'no' (though you won't get any groups then).

        Allocations which are included in this way will return True in the
        following expression:

        getattr(allocation, 'is_extra_result', False)

        :start:
            Include allocations starting on or after this date.

        :end:
            Include allocations ending on or before this date.

        :days:
            List of days which should be considered, a subset of:
            (['mo', 'tu', 'we', 'th', 'fr', 'sa', 'su'])

            If left out, all days are included.

        :minspots:
            Minimum number of spots reservable.

        :available_only:
            If True, unavailable allocations are left out
            (0% availability). Default is False.

        :whole_day:
            May have one of the following values: 'yes', 'no', 'any'

            If yes, only whole_day allocations are returned.
            If no, whole_day allocations are filtered out.
            If any (default), all allocations are included.

            Any is the same as leaving the option out.

        :include_groups:
            'any' if all allocations should be included.
            'yes' if only group-allocations should be included.
            'no' if no group-allocations should be included.

            See allocation.in_group to see what constitutes a group

        :strict:
            Set to True if you don't want groups included as a whole if a
            groupmember is found. See comment above.
        """

        assert start
        assert end

        assert whole_day in ('yes', 'no', 'any')
        assert groups in ('yes', 'no', 'any')

        if days:
            days_map = {
                'mo': 0,
                'tu': 1,
                'we': 2,
                'th': 3,
                'fr': 4,
                'sa': 5,
                'su': 6
            }

            # get the day from the map - if impossible take the verbatim value
            # this allows for using strings or integers
            days = set(days_map.get(day, day) for day in days)

        query = self.allocations_in_range(start, end)
        query = query.order_by(Allocation._start)

        allocations = []

        known_groups = set()
        known_ids = set()

        for allocation in query.all():

            if not self.is_exposed(allocation):
                continue

            s = datetime.combine(allocation.start.date(), start.time())
            e = datetime.combine(allocation.end.date(), end.time())

            if not allocation.overlaps(s, e):
                continue

            if days:
                if allocation.start.weekday() not in days:
                    continue

            if whole_day != 'any':
                if whole_day == 'yes' and not allocation.whole_day:
                    continue
                if whole_day == 'no' and allocation.whole_day:
                    continue

            # minspots means that we don't show allocations which cannot
            # be reserved with the required spots in one reservation
            # so we can disregard all allocations with a lower quota limit.
            #
            # the spots are later checked again for actual availability, but
            # that is a heavier check, so it doesn't belong here.
            if minspots:
                if allocation.reservation_quota_limit > 0:
                    if allocation.reservation_quota_limit < minspots:
                        continue

            if available_only:
                if not self.find_spot(allocation, s, e):
                    continue

            if minspots:
                availability = self.availability(
                    allocation.start, allocation.end
                )

                if (minspots / float(allocation.quota) * 100.0) > availability:
                    continue

            # keep track of allocations in groups as those need to be added
            # to the result, even though they don't match the search
            in_group = (
                allocation.group in known_groups or allocation.in_group
            )

            if in_group:
                known_groups.add(allocation.group)
                known_ids.add(allocation.id)

            if groups != 'any':
                if groups == 'yes' and not in_group:
                    continue
                if groups == 'no' and in_group:
                    continue

            allocations.append(allocation)

        if not strict and groups != 'no' and known_ids and known_groups:
            query = self.managed_allocations()
            query = query.filter(not_(Allocation.id.in_(known_ids)))
            query = query.filter(Allocation.group.in_(known_groups))

            for allocation in query.all():
                allocation.is_extra_result = True
                allocations.append(allocation)

            allocations.sort(key=lambda a: a._start)

        return allocations

    def free_allocations_count(self, master_allocation, start, end):
        """ Returns the number of free allocations between master_allocation
        and it's mirrors. """

        free_allocations = 0

        if master_allocation.is_available(start, end):
            free_allocations += 1

        if master_allocation.quota == 1:
            return free_allocations

        for mirror in self.allocation_mirrors_by_master(master_allocation):
            if mirror.is_available(start, end):
                free_allocations += 1

        return free_allocations

    def reservation_targets(self, start, end):
        """ Returns a list of allocations that are free within start and end.
        These allocations may come from the master or any of the mirrors.

        """
        targets = []

        query = all_allocations_in_range(start, end)
        query = query.filter(Allocation.resource == self.uuid)

        for master_allocation in query:

            if not master_allocation.overlaps(start, end):
                continue  # may happen because start and end are not rasterized

            found = self.find_spot(master_allocation, start, end)

            if not found:
                raise AlreadyReservedError

            targets.append(found)

        return targets

    def reserved_slots_by_reservation(self, token, id=None):
        """ Returns all reserved slots of the given reservation.
        The id is optional and may be used only return the slots from a
        specific reservation matching token and id.
        """

        assert token

        query = self.managed_reserved_slots()
        query = query.filter(ReservedSlot.reservation_token == token)

        if id is None:
            return query
        else:
            ids = self.allocations_by_reservation(token, id)
            ids = ids.with_entities(Allocation.id)
            return query.filter(
                ReservedSlot.allocation_id.in_(ids.subquery())
            )

    def reservations_by_token(self, token, id=None):
        query = self.managed_reservations()
        query = query.filter(Reservation.token == token)

        if id:
            query = query.filter(Reservation.id == id)

        try:
            query.first()
        except exc.NoResultFound:
            raise InvalidReservationToken

        return query

    def reservations_by_group(self, group):
        tokens = self.managed_reservations().with_entities(Reservation.token)
        tokens = tokens.filter(Reservation.target == group)

        return self.managed_reservations().filter(
            Reservation.token.in_(
                tokens.subquery()
            )
        )

    def reservations_by_allocation(self, allocation_id):
        master = self.allocation_by_id(allocation_id)

        return self.reservations_by_group(master.group)
