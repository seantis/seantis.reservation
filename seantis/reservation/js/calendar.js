if (!this.seantis) this.seantis = {};
if (!this.seantis.calendar) this.seantis.calendar = {};

// Adds a plone overlay to a form view.
// Submitting the form will forche the calendar to refetch the events
seantis.calendar.form_overlay = function(element) {
    element.prepOverlay({
        subtype: 'ajax',
        filter: '#content>*',
        formselector: 'form',
        noform: 'close',
        config: {
            onClose: function() {
                var calendar = $(seantis.calendar.id);
                calendar.fullCalendar('refetchEvents');    
            }
        }
    });
};

(function($) {
    $(document).ready(function() {
        if (!seantis || !seantis.calendar || !seantis.calendar.id)
            return;

        var show_overlay = function(url) {
            var link = $('<a href="' + url + '"></a>');
            seantis.calendar.form_overlay(link);
            
            link.click();  
        };

        // Prepares the contextmenu for the event and adds the form overlay
        var eventRender = function(event, element) {
            var menuitems = [];

            var reserve = '<a class="seantis-reservation-reserve" ';
            reserve += 'href="' + event.url + '">';
            reserve += seantis.locale('reserve') + '</a>';
            menuitems.push(reserve);

            var edit = '<a class="seantis-reservation-edit" ';
            edit += 'href="' + event.editurl + '">';
            edit += seantis.locale('edit') + '</a>';
            menuitems.push(edit);

            if (event.groupurl) {
                var group = '<a class="seantis-reservation-group" ';
                group += 'href="' + event.groupurl + '">';
                group += seantis.locale('group') + '</a>';
                menuitems.push(group);
            }

            var menuhtml = '';
            for (var i=0; i<menuitems.length; i++) {
                menuhtml += '<p>' + menuitems[i] + '</p>';
            }

            seantis.contextmenu(element, menuhtml);
            seantis.calendar.form_overlay(element);
        };

        var moveEvent = function(event) {
            var url = event.editurl;
            url += '&start=' + event.start.getTime() / 1000;
            url += '&end=' + event.end.getTime() / 1000;
            
            show_overlay(url);
        };

        var eventResize = function(
            event, dayDelta, minuteDelta, revertFunc, jsEvent, ui, view) {
            
            moveEvent(event);
        };

        var eventDrop = function(
            event, dayDelta, minuteDelta, allDay, revertFunc, jsEvent, ui, view) {
            
            moveEvent(event);
        };

        // Called when a selection on the calendar is made
        // TODO do not execute if the permissions are insufficient
        var eventAdd = function(start, end, allDay) {
            if (allDay) return;

            var url = seantis.calendar.allocateurl;
            url += '?start=' + start.getTime() / 1000;
            url += '&end=' + end.getTime() / 1000;

            show_overlay(url);
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
            selectable: true,
            selectHelper: true,
            select: eventAdd,
            editable: true,
            eventRender: eventRender,
            eventResize: eventResize,
            eventDrop: eventDrop
        };

        // Merge the options with the ones defined by the resource view
        $.extend(options, seantis.calendar.options);

        $(seantis.calendar.id).fullCalendar(options);
    });
})( jQuery );