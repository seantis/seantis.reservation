if (!this.seantis) this.seantis = {};
if (!this.seantis.calendar) this.seantis.calendar = {};

seantis.calendar.form_overlay = function(element) {
    element.prepOverlay({
        subtype: 'ajax',
        filter: '#content>*',
        formselector: 'form',
        noform: function() {
            $(seantis.calendar.id).fullCalendar('refetchEvents');
            return 'close';
        }
    });
};

(function($) {
    $(document).ready(function() {
        if (!seantis || !seantis.calendar || !seantis.calendar.id)
            return;

        var eventRender = function(event, element) {
            var reserve = '<a class="seantis-reservation-reserve" ';
            reserve += 'href="' + event.url + '">';
            reserve += seantis.locale('reserve') + '</a>';

            seantis.contextmenu(element, reserve);
            seantis.calendar.form_overlay(element);
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
            eventRender: eventRender
        };

        $.extend(options, seantis.calendar.options);

        $(seantis.calendar.id).fullCalendar(options);
    });
})( jQuery );