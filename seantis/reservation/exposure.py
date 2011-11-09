from zope.security import checkPermission
from zope.component import getMultiAdapter

from seantis.reservation import utils
from seantis.reservation.timeframe import timeframes_by_context

def for_allocations(context, resources):
    """Returns a function which takes an allocation and returns true if the
    allocation can be exposed.

    """

    get_obj = lambda uuid: utils.get_resource_by_uuid(context, uuid).getObject()
    resource_objects = dict([(uuid, get_obj(uuid)) for uuid in resources])

    timeframes = {}

    for uuid, resource in resource_objects.items():
        timeframes[uuid] = timeframes_by_context(resource)

    def is_exposed(allocation):
        frames = timeframes[str(allocation.mirror_of)]

        if not frames:
            return True

        day = allocation.start.date()
        for frame in frames:
            if frame.start <= day and day <= frame.end:
                return frame.visible()

        return False

    return is_exposed

def for_views(context, request):
    get_view = lambda name: getMultiAdapter((context, request), name=name)

    def is_exposed(viewname):
        view = get_view(viewname)
        assert hasattr(view, 'permission'), "missing permission attribute"
        return checkPermission(view.permission, view)

    return is_exposed