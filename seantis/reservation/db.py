import transaction

from logging import getLogger
log = getLogger('seantis.reservation')

from uuid import UUID, uuid1 as new_uuid
from datetime import datetime, timedelta, MINYEAR, MAXYEAR
from itertools import groupby

from zope.event import notify

from sqlalchemy.sql import and_, or_
from sqlalchemy.orm import joinedload, exc
from sqlalchemy import func, null

from seantis.reservation.events import (
    ReservationApprovedEvent,
    ReservationDeniedEvent,
    ReservationMadeEvent,
    ReservationRevokedEvent,
    ReservationsConfirmedEvent,
    ReservationSlotsCreatedEvent,
    ReservationSlotsRemovedEvent,
    ReservationSlotsUpdatedEvent,
    ReservationUpdatedEvent,
)

from seantis.reservation.models import (
    Allocation, BlockedPeriod, ReservedSlot, Reservation, Recurrence
)

from seantis.reservation.error import (
    AffectedPendingReservationError,
    AffectedReservationError,
    AlreadyReservedError,
    InvalidAllocationError,
    InvalidQuota,
    InvalidReservationError,
    InvalidReservationToken,
    NoRecurringReservationError,
    NoReservedSlotsLeftError,
    NotReservableError,
    OverlappingAllocationError,
    QuotaImpossible,
    QuotaOverLimit,
    ReservationError,
    ReservationOutOfBounds,
    ReservationParametersInvalid,
    ReservationTooLong,
    UnblockableAlreadyReservedError,
)

from seantis.reservation.session import serialized
from seantis.reservation.raster import rasterize_span, MIN_RASTER_VALUE
from seantis.reservation.interfaces import validate_email
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


@serialized
def unblock_periods(reservation):
    """Unblock periods for any resource based on a reservation.

    """
    if not utils.is_uuid(reservation):
        reservation = reservation.token
    query = Session.query(BlockedPeriod).filter_by(token=reservation)
    query.delete('fetch')


@serialized
def remove_orphan_recurrences():
    orphans = Session.query(Recurrence).filter(~Recurrence.allocations.any())
    orphans.delete(synchronize_session=False)


def grouped_reservation_view(query):
    """Takes a query of reserved slots joined with allocations and uses it
    to return reservation uuid, allocation id and the start and end dates
    within the referenced allocation.

    If the above sentence does not make sense: It essentialy builds the data
    needed for the ManageReservationsForm.

    """
    query = query.with_entities(
        ReservedSlot.reservation_token,
        Allocation.id,
        func.min(ReservedSlot.start),
        func.max(ReservedSlot.end)
    )
    query = query.group_by(ReservedSlot.reservation_token, Allocation.id)
    query = query.order_by(
        ReservedSlot.reservation_token, 'min_1', Allocation.id
    )

    return query


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

    for reservation in reservations:
        reservation.session_id = None

    notify(ReservationsConfirmedEvent(reservations, language))


@serialized
def remove_reservation_from_session(session_id, token):
    """ Removes the reservation with the given session_id and token. """

    assert token and session_id

    query = reservations_by_session(session_id)
    query = query.filter(Reservation.token == token)

    reservation = query.one()
    Session.delete(reservation)

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
    scheduler.managed_blocked_periods().delete('fetch')

    remove_orphan_recurrences()


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

    def managed_blocked_periods(self):
        """ The block_periods managed by this scheduler / resource. """
        query = Session.query(BlockedPeriod)
        query = query.filter(BlockedPeriod.resource == self.uuid)

        return query

    @serialized
    def allocate(self, dates, raster=15, quota=None, partly_available=False,
                 grouped=False, approve_manually=True,
                 reservation_quota_limit=0, whole_day=False, rrule=None
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
        # use recurrence to group separate allocations.
        if not grouped and len(dates) > 1:
            recurrence = Recurrence(rrule=rrule)
        else:
            recurrence = None
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
            allocation.recurrence = recurrence
            if grouped:
                allocation.group = group
            else:
                allocation.group = new_uuid()

            allocations.append(allocation)

        if recurrence:
            Session.add(recurrence)
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

    def allocations_by_group(self, group, masters_only=True):
        query = self.managed_allocations()
        query = query.filter(Allocation.group == group)

        if masters_only:
            query = query.filter(Allocation.resource == self.uuid)

        return query

    def allocations_by_recurrence(self, recurrence_id):
        query = self.managed_allocations()
        query = query.filter_by(recurrence_id=recurrence_id)
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

    def allocations_by_reservation(self, reservation_token):
        query = self.managed_allocations()
        query = query.join(ReservedSlot)
        query = query.filter(
            ReservedSlot.reservation_token == reservation_token
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
    def remove_allocation(self, id=None, group=None, recurrence_id=None):
        if recurrence_id:
            allocations = self.allocations_by_recurrence(recurrence_id).all()
        elif group:
            allocations = self.allocations_by_group(group, masters_only=False)\
                              .all()
        elif id:
            master = self.allocation_by_id(id)
            allocations = [master]
            allocations.extend(self.allocation_mirrors_by_master(master))
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
        
        remove_orphan_recurrences()

    def _reserve_sanity_check(self, dates, quota):
        """Check the request for saneness. If any requested date cannot be
        reserved the request as a whole fails.

        """
        for start, end in dates:

            # are the parameters valid?
            if abs((end - start).days) >= 1:
                raise ReservationTooLong

            if start > end or (end - start).seconds < 5 * 60:
                raise ReservationParametersInvalid

            has_allocation = False
            # can all allocations be reserved?
            for allocation in self.allocations_in_range(start, end):

                # start and end are not rasterized, so we need this check
                if not allocation.overlaps(start, end):
                    continue

                if not allocation.contains(start, end):
                    continue

                has_allocation = True
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

            # if we did not find an allocation for a start/end pair
            if not has_allocation:
                raise ReservationOutOfBounds

    def _create_reservation(self, email, dates, group, data, session_id,
                            quota, rrule, token, description):
        reservation = None
        # groups are reserved by group-identifier - so all members of a group
        # or none of them. As such there's no start / end date which is defined
        # implicitly by the allocation
        if group:
            reservation = Reservation.for_group(group)

        # XXX i'm confused and/or unhappy about this code.
        # - we iterate dates and could theoretically create more than one
        #   reservation, but in the end it (approval) only works with one
        #   it feels like there should be a better way?

        elif rrule:
            assert len(dates) > 1, """
                recurrence only makes sense for multiple dates
            """

            target_start, target_end = dates[0]
            for allocation in self.allocations_in_range(target_start,
                                                        target_end):

                    if not allocation.overlaps(target_start, target_end):
                        continue

                    reservation = Reservation.for_recurrence(rrule)
                    reservation.start, reservation.end = rasterize_span(
                        target_start, target_end, allocation.raster
                    )
                    # XXX do we need a target in this case?
                    reservation.target = allocation.group

        else:
            groups = []
            for start, end in dates:
                for allocation in self.allocations_in_range(start, end):

                    if not allocation.overlaps(start, end):
                        continue

                    assertion_msg = "can't create multiple reservations"
                    assert reservation is None, assertion_msg

                    reservation = Reservation.for_allocation(allocation)
                    reservation.start, reservation.end = rasterize_span(
                        start, end, allocation.raster
                    )
                    groups.append(allocation.group)

                # check if no group reservation is made with this request.
                # reserve by group in this case (or make this function
                # do that automatically)
                assert len(groups) == len(set(groups)), \
                    'wrongly trying to reserve a group'

        if reservation:
            reservation.token = token
            reservation.email = email
            reservation.quota = quota
            reservation.session_id = session_id
            reservation.data = data
            reservation.resource = self.uuid
            reservation.description = description
        return reservation

    @serialized
    def reserve(self, email, dates=None, group=None, data=None,
                session_id=None, quota=1, rrule=None, description=None):
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
        token = new_uuid()

        self._reserve_sanity_check(dates, quota)
        reservation = self._create_reservation(email, dates, group, data,
                                               session_id, quota, rrule, token,
                                               description)
        if reservation:
            Session.add(reservation)
            notify(ReservationMadeEvent(reservation, self.language))
        else:
            raise InvalidReservationError

        return token

    @serialized
    def generate_reserved_slots(self, token, reservation, dates=None):
        slots_to_reserve = []

        if dates is None:
            dates = reservation.target_dates()
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
                    slot.reservation_token = token

                    # the slots are written with the allocation
                    allocation.reserved_slots.append(slot)
                    slots_to_reserve.append(slot)

                # the allocation may be a fake one, in which case we
                # must make it realz yo
                if allocation.is_transient:
                    Session.add(allocation)
        return slots_to_reserve

    @serialized
    def approve_reservation(self, token):
        """ This function approves an existing reservation and writes the
        reserved slots accordingly.

        Returns a list with the reserved slots.

        """
        reservation = self.reservation_by_token(token).one()

        # return these slots
        slots_to_reserve = self.generate_reserved_slots(token, reservation)

        reservation.status = u'approved'

        if not slots_to_reserve:
            raise NotReservableError

        notify(ReservationSlotsCreatedEvent(reservation, self.language))
        notify(ReservationApprovedEvent(reservation, self.language))

        return slots_to_reserve

    @serialized
    def deny_reservation(self, token):
        """ Denies a pending reservation, removing it from the records and
        sending an email to the reservee.

        """

        query = self.reservation_by_token(token)
        query.filter(Reservation.status == u'pending')

        reservation = query.one()
        Session.delete(reservation)

        notify(ReservationDeniedEvent(reservation, self.language))

    @serialized
    def revoke_reservation(self, token, reason, send_email=True):
        """ Revoke a reservation and inform the user of that."""

        reason = reason or u''

        # sending the email first is no problem as it won't work if
        # an exception triggers later in the request
        reservation = self.reservation_by_token(token).one()
        notify(ReservationRevokedEvent(
            reservation, self.language, reason, send_email
        ))

        self.remove_reservation(token)

    @serialized
    def remove_reservation(self, token):
        """ Removes all reserved slots of the given reservation token.

        Removes all blocked periods related to this reservation as well.

        Note that removing a reservation does not let the reservee know that
        his reservation has been removed.

        If you want to let the reservee know what happened,
        use revoke_reservation.

        """

        slots = self.reserved_slots_by_reservation(token)
        slots.delete('fetch')

        unblock_periods(token)

        self.reservation_by_token(token).delete()

    @serialized
    def remove_reservation_slots(self, token, start, end):
        """ Removes all reserved slots of the given reservation token
        between start and end.

        Note that removing a reservation does not let the reservee know that
        his reservation has been removed.

        """
        reservation = self.reservation_by_token(token).one()
        if not reservation.is_recurrence:
            raise NoRecurringReservationError

        query = self.reserved_slots_by_reservation(token)
        query_slots_left = query.filter(or_(ReservedSlot.end > end,
                                            ReservedSlot.start < start))
        if query_slots_left.first() is None:
            raise NoReservedSlotsLeftError

        query_remove = query.filter(ReservedSlot.start >= start)\
                            .filter(ReservedSlot.end <= end)

        dates = []
        for date, group in groupby(query_remove.order_by(ReservedSlot.start),
                                   lambda slot: slot.start.date()):
            entries = list(group)  # iterators are empty after one iteration
            start = min(each.start for each in entries)
            end = max(each.end for each in entries)
            dates.append((start, end))

        notify(ReservationSlotsRemovedEvent(reservation, self.language, dates))

        query_remove.delete('fetch')

    def _update_reserved_slots(self, start, end, reservation):
        """re-generate reserved slots.

        we could detect the diff and only update the changes, but this is
        way too complicated at the moment.

        """
        changed = False
        token = reservation.token
        new_start, new_end = utils.as_machine_date(start, end)
        if reservation.start != new_start or reservation.end != new_end:
            changed = True
            query = self.managed_reserved_slots()
            query = query.filter_by(reservation_token=token)

            assert reservation.autoapprovable, """
                can't change start/end-time for reservations
                that are not autoapprovable
            """

            assert not reservation.is_group, """"
                can't change start/end-time for reservations
                that target a group
            """

            if reservation.is_recurrence:
                start_time = new_start.time()
                end_time = new_end.time()
                current_reservations = reservation.timespans()

                for old_start, old_end in current_reservations:
                    old_start, old_end = utils.as_machine_date(
                        old_start, old_end
                    )
                    query_del = query.filter(ReservedSlot.start >= old_start)\
                                     .filter(ReservedSlot.end <= old_end)
                    query_del.delete('fetch')

                    date = old_start.date()
                    dates = [utils.get_date_range(date, start_time, end_time)]
                    self._reserve_sanity_check(dates, reservation.quota)
                    self.generate_reserved_slots(token, reservation, dates)
                reservation.start = new_start
                reservation.end = new_end
            elif reservation.is_allocation:
                query.delete('fetch')
                reservation.start = start
                reservation.end = end
                self._reserve_sanity_check([(start, end)], reservation.quota)
                self.generate_reserved_slots(token, reservation)

        return changed

    @serialized
    def update_reservation(self, token, start, end, email, description, data):
        time_changed = False
        reservation = self.reservation_by_token(token).one()
        old_data = reservation.data
        data_changed = self.update_reservation_data(token, data)

        if reservation.email != email:
            reservation.email = email
            data_changed = True
        if reservation.description != description:
            reservation.description = description
            data_changed = True

        try:
            time_changed = self._update_reserved_slots(
                start, end, reservation
            )
        except ReservationError:
            transaction.abort()
            raise

        if time_changed:
            notify(ReservationSlotsUpdatedEvent(reservation, self.language))
        if time_changed or data_changed:
            notify(ReservationUpdatedEvent(reservation, self.language,
                                           old_data, time_changed))

    @serialized
    def update_reservation_data(self, token, data):
        reservation = self.reservation_by_token(token).one()

        # make sure data not coming from a form is preserved. Use new instance
        # to make sure sqlalchemy detects the modification.
        # somehow setting instance_state(reservation).modified = True does not
        # work, thus we need this workaround.
        old_data = reservation.data
        new_data = dict()
        if old_data:
            new_data.update(old_data)
        new_data.update(data)

        reservation.data = new_data
        return new_data != old_data

    @serialized
    def confirm_reservations_for_session(self, session_id, token=None):
        """ Confirms all reservations of the given session id. Optionally
        confirms only the reservations with the given token. All if None.

        """

        assert session_id

        reservations = reservations_by_session(session_id)

        if token:
            reservations = reservations.filter(Reservation.token == token)

        reservations = reservations.all()

        for reservation in reservations:
            reservation.session_id = None

        notify(ReservationsConfirmedEvent(reservations, self.language))

    @serialized
    def remove_reservation_from_session(self, session_id, token):
        """ Removes the reservation with the given session_id and token. """

        assert token and session_id

        # XXX could we use self.remove_session for the middle part?
        query = reservations_by_session(session_id)
        query = query.filter(Reservation.token == token)

        reservation = query.one()
        Session.delete(reservation)

        # if we get here the token must be valid, we should then check if the
        # token is used in the reserved slots, because with autoapproval these
        # slots may be created straight away.

        slots = Session.query(ReservedSlot).filter(
            ReservedSlot.reservation_token == token
        )

        slots.delete('fetch')

        # the blocking periods for this reservation might have already been
        # generated by some third party library. They must be removed as well.
        unblock_periods(reservation)

        # we also update the timestamp of existing reservations within
        # the same session to ensure that we account for the user's activity
        # properly during the session expiration cronjob. Otherwise it is
        # possible that a user removes the latest reservations only to see
        # the rest of them vanish because his older reservations were
        # already old enough to be counted as expired.

        query = Session.query(Reservation)
        query = query.filter(Reservation.session_id == session_id)

        query.update({"modified": utils.utcnow()})

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

    def reserved_slots_by_reservation(self, reservation_token):
        """Returns all reserved slots of the given reservation."""

        assert reservation_token

        query = self.managed_reserved_slots()
        query = query.filter(
            ReservedSlot.reservation_token == reservation_token
        )

        return query

    def reserved_slots_by_group(self, group):
        query = self.managed_reserved_slots()
        query = query.filter(Allocation.group == group)

        return query

    def reserved_slots_by_allocation(self, allocation_id):
        master = self.allocation_by_id(allocation_id)
        mirrors = self.allocation_mirrors_by_master(master)
        ids = [master.id] + [m.id for m in mirrors]

        query = self.managed_reserved_slots()
        query = query.filter(ReservedSlot.allocation_id.in_(ids))

        return query

    def reservation_by_token(self, token):
        query = self.managed_reservations()
        query = query.filter(Reservation.token == token)

        try:
            query.one()
        except exc.NoResultFound:
            raise InvalidReservationToken
        except exc.MultipleResultsFound:
            raise NotImplementedError

        return query

    def reservations_by_group(self, group):
        query = self.managed_reservations()
        query = query.filter(Reservation.target == group)

        return query

    def reservations_by_recurring_allocation(self, allocation_id):
        """Find reservations that target an allocation thats part of a
        recurrence.

        """
        master = self.allocation_by_id(allocation_id)
        tokens = [slot.reservation_token for slot in master.reserved_slots]

        query = self.managed_reservations()

        if not tokens:
            return query.filter(Reservation.target == master.group)
        else:
            return query.filter(
                or_(
                    Reservation.token.in_(tokens),
                    Reservation.target == master.group
                )
            )

    def reservations_by_allocation(self, allocation_id):
        master = self.allocation_by_id(allocation_id)

        return self.reservations_by_group(master.group)

    def has_reserved_slot_in_range(self, start, end):
        assert start and end

        query = self.managed_reserved_slots()
        query = query.filter(start <= ReservedSlot.start)
        query = query.filter(ReservedSlot.end <= end)

        for slot in query:
            if slot.allocation.overlaps(start, end):
                return True

        return False

    @serialized
    def block_periods(self, reservation):
        """Block periods for the scheduler's resource based on another
        reservation.

        """
        for start, end in reservation.timespans():
            self.block_period(start, end, reservation.token)

    @serialized
    def block_period(self, start, end, token):
        """Block the period from start to end for the scheduler's resource.

        """
        start, end = utils.as_machine_date(start, end)

        if self.has_reserved_slot_in_range(start, end):
            raise UnblockableAlreadyReservedError

        blocked_period = BlockedPeriod(
            resource=self.uuid,
            token=token,
            start=start,
            end=end
        )
        Session.add(blocked_period)
