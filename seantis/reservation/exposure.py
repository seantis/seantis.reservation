from uuid import UUID

from zope.security import checkPermission
from zope.component import getMultiAdapter

from seantis.reservation.utils import is_uuid, get_resource_by_uuid
from seantis.reservation.utils import string_uuid, real_uuid
from seantis.reservation.timeframe import timeframes_by_context


def for_allocations(resources):
    """Returns a function which takes an allocation and returns true if the
    allocation can be exposed.

    resources can be a list of uuids or a list of resource objects

    """

    # get a dictionary with uuids as keys and resources as values
    def get_object(obj):
        if is_uuid(obj):
            return UUID(obj), get_resource_by_uuid(obj)
        else:
            return UUID(obj.uuid()), obj

    resource_objects = dict([get_object(o) for o in resources])

    # get timeframes for each uuid
    timeframes = {}
    for uuid, resource in resource_objects.items():

        # Don't load the timeframes of the resources for which the user has
        # special access to. This way they won't get checked later in
        # 'is_exposed'
        if checkPermission(
                'seantis.reservation.ViewHiddenAllocations', resource):
            timeframes[uuid] = []
        elif resource is None:
            timeframes[uuid] = [None]
        else:
            timeframes[uuid] = timeframes_by_context(resource)

    # returning closure
    def is_exposed(allocation):

        # use the mirror_of as resource-keys of mirrors do not really exist
        # as plone objects
        frames = timeframes[allocation.mirror_of]

        if frames is None or len(frames) == 0:
            return True

        if frames == [None]:
            return False

        # the start date is relevant
        day = allocation.start.date()
        for frame in frames:
            if frame.start <= day and day <= frame.end:
                return frame.visible()

        return False

    return is_exposed


def for_views(context, request):
    """Returns a function which takes a viewname and returns true if the user
    has the right to see the view.

    """

    # gets an instance of the view
    get_view = lambda name: getMultiAdapter((context, request), name=name)

    def is_exposed(viewname):
        view = get_view(viewname)
        assert hasattr(view, 'permission'), "missing permission attribute"

        return checkPermission(view.permission, view)

    return is_exposed


def for_calendar(resource):
    """Returns a function which takes a calendar option and returns true
    if it is enabled.

    """

    option_permissions = {
        'selectable': 'cmf.AddPortalContent',  # drag and drop creation
        'editable': 'cmf.ModifyPortalContent',  # drag and drop resizing
    }

    # right now there's nothing sophisticated to see here
    def is_exposed(option):
        if option in option_permissions:
            return checkPermission(option_permissions[option], resource)
        else:
            return False

    return is_exposed


def for_resources(resources):
    """Returns a function which takes a resource (object or uuid) and
    returns true if it is visible to the current user.

    """

    visible_resources = []

    for r in resources:
        if checkPermission('zope2.View', r):
            visible_resources.append(string_uuid(r))

    def is_exposed(resource):
        return string_uuid(resource) in visible_resources

    return is_exposed


def limit_resources(resources):
    """Given a list of resources or a dictionary with uuid -> resources,
    this function will return the subset of the argument depending on the
    result of for_resource_reservations.is_exposed.

    """

    is_dict = isinstance(resources, dict)
    is_list = isinstance(resources, (list, tuple, set))

    assert is_dict or is_list

    if is_list:
        resdict = dict(((real_uuid(r), r) for r in resources))
    else:
        resdict = resources

    is_exposed = for_resources(resdict.values())

    to_remove = []

    for key, resource in resdict.items():
        if not is_exposed(resource):
            to_remove.append(key)

    for key in to_remove:
        del resdict[key]

    if is_list:
        return resdict.values()
    else:
        return resdict
