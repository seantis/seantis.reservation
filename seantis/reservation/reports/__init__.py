from seantis.reservation import (
    form,
    utils
)

from seantis.reservation import _


class GeneralReportParametersMixin(
    form.ReservationDataView,
    form.ResourceParameterView
):

    titles = {}

    def resource_title(self, uuid):
        if not uuid in self.titles:
            self.titles[uuid] = utils.get_resource_title(self.resources[uuid])
        
        return self.titles[uuid]
    
    @property
    def statuses(self):
        return (
            ('pending', _(u'Pending')),
            ('approved', _(u'Approved')),
        )

    @property
    def hidden_statuses(self):
        return utils.pack(self.request.get('hide_status', []))

    @property
    def reservations(self):
        return utils.pack(self.request.get('reservations', []))

    @property
    def sorted_resources(self):
        objs = self.resources

        sortkey = lambda item: self.resource_title(item[0])
        return utils.OrderedDict(sorted(objs.items(), key=sortkey))

    @property
    def hidden_resources(self):
        return utils.pack(self.request.get('hide_resource', []))

    @property
    def show_details(self):
        # show_details is the query parameter as hiding is the default
        return True if self.request.get('show_details') else False

    @utils.cached_property
    def data_macro_path(self):
        resource = self.resources[self.uuids[0]]
        url = resource.absolute_url() + \
            '/@@reservations/macros/reservation_data'

        return url.replace(self.context.absolute_url(), 'context')

    def show_status(self, status):
        return status not in self.hidden_statuses

    def show_resource(self, uuid):
        return uuid not in self.hidden_resources

    def build_url(self, extra_parameters=None):

        url = '{}/{}'.format(self.context.absolute_url(), self.__name__)
        params = []

        if self.show_details:
            params.append(('show_details', '1'))

        for status in self.hidden_statuses:
            params.append(('hide_status', status))

        for resource in self.hidden_resources:
            params.append(('hide_resource', resource))

        for uuid in self.uuids:
            params.append(('uuid', uuid))

        if extra_parameters:
            params.extend(extra_parameters)

        pair = lambda item: '='.join(item)
        return '{}?{}'.format(url, '&'.join(map(pair, params)))
