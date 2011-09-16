if (!this.seantis) this.seantis = {};
if (!this.seantis.calendar) this.seantis.calendar = {};

// Adds a plone overlay to a form view.
// Submitting the form will forche the calendar to refetch the events
seantis.calendar.form_overlay = function(element) {
    element.prepOverlay({
        subtype: 'ajax',
        filter: '#content>*',
        formselector: 'form',
        noform: function() {
            var calendar = $(seantis.calendar.id);
            calendar.fullCalendar('refetchEvents');
            return 'close';
        }
    });
};

(function($) {
    $(document).ready(function() {
        if (!seantis || !seantis.calendar || !seantis.calendar.id)
            return;

        // Prepares the contextmenu for the event and adds the form overlay
        var eventRender = function(event, element) {
            var reserve = '<p><a class="seantis-reservation-reserve" ';
            reserve += 'href="' + event.url + '">';
            reserve += seantis.locale('reserve') + '</a></p>';

            var edit = '<p><a class="seantis-reservation-edit" ';
            edit += 'href="' + event.editurl + '">';
            edit += seantis.locale('edit') + '</a></p>';

            seantis.contextmenu(element, reserve + edit);
            seantis.calendar.form_overlay(element);
        };

        // Called when a selection on the calendar is made
        // TODO do not execute if the permissions are insufficient
        var eventAdd = function(start, end, allDay) {
            if (allDay) return;

            var url = seantis.calendar.allocateurl;
            url += '?start=' + start.getTime() / 1000;
            url += '&end=' + end.getTime() / 1000;

            var link = $('<a href="' + url + '"></a>');
            seantis.calendar.form_overlay(link);

            link.click();
        };

        var options = {
            header: {
                left: 'prev, next today',
                right: 'month, agendaWeek, agendaDay'
            },
            defaultView: 'agendaWeek',
            timeFormat: 'HH:mm{ - HH:mm}',
            axisFormat: 'HH:mm{ - HH:mm}',
            columnFormat: 'dddd d.M',
            allDaySlot: false,
            firstDay: 1,
            eventRender: eventRender,
            selectable: true,
            selectHelper: true,
            select: eventAdd
        };

        // Merge the options with the ones defined by the resource view
        $.extend(options, seantis.calendar.options);

        $(seantis.calendar.id).fullCalendar(options);
    });
})( jQuery );