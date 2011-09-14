(function($) {
    $(document).ready(function() {
        if (!seantis || !seantis.calendar)
            return;

        var eventRender = function(event, element) {
            var reserve = '<a href="' + event.url + '">';
            reserve += seantis.locale('reserve') + '</a>';

            seantis.contextmenu(element, reserve);
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