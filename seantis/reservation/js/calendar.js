if (!this.seantis) this.seantis = {};
if (!this.seantis.calendars) this.seantis.calendars = [];

(function($) {
    $(document).ready(function() {

        if (!seantis.calendars.length)
            return;

        // Adds commonly used functions to the calendars and provides an easy
        // way to iterate over them. 
        var foreachcalendar = function(callback) {
            for (var i=0; i < seantis.calendars.length; i++) {

                var calendar = seantis.calendars[i];

                // Add jquery element
                if (typeof calendar.element === 'undefined') {
                    calendar.element = $(calendar.id);
                }

                // Add index
                if (typeof calendar.index == 'undefined') {
                    calendar.index = i;
                }

                // Add form_overlay function which automatically refetches events
                if (typeof calendar.form_overlay == 'undefined') {
                    calendar.form_overlay = function(element) {
                        var calendar = this;
                        element.prepOverlay({
                           subtype: 'ajax', filter:  '#content>*',
                           formselector: 'form', noform: 'close',
                           config: { 
                                onClose: function() {
                                    calendar.element.fullCalendar('refetchEvents');
                                }
                           } 
                        });
                    };
                }

                // Add show_overlay function
                if (typeof calendar.show_overlay == 'undefined') {
                    calendar.show_overlay = function(url) {
                        var link = $('<a href="' + url + '"></a>');
                        this.form_overlay(link);
                        link.click();
                    };
                }

                // Callback using the calendar object with the added functions
                callback(seantis.calendars[i]);
            }  
        };

        var renderEvent = function(event, element, calendar) {

            // Add contextmenu items

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

            seantis.contextmenu(element, menuhtml, calendar.index);
            calendar.form_overlay(element);

            // Add partitions

            var partitions = '';
            for (i = 0; i<event.partitions.length; i++) {
                var partition = event.partitions[i];
                var reserved = partition[1];
                var percentage = partition[0];

                if (reserved === false) {
                    partitions += '<div style="height:' + percentage + '%"></div>';
                } else {
                    partitions += '<div style="height:' + percentage + '%" ';
                    partitions += 'class="calendarOccupied"></div>';
                }
            }

            $('.fc-event-bg', element).wrapInner(partitions);
        };

        // Called when an event is resized or moved
        var moveEvent = function(event, calendar) {
            var url = event.editurl;
            url += '&start=' + event.start.getTime() / 1000;
            url += '&end=' + event.end.getTime() / 1000;
            
            calendar.show_overlay(url);
        };

        // Called when a selection on the calendar is made
        var eventAdd = function(start, end, allDay, calendar) {

            // TODO do not execute if the permissions are insufficient
            if (allDay) return;

            var url = calendar.allocateurl;
            url += '?start=' + start.getTime() / 1000;
            url += '&end=' + end.getTime() / 1000;

            calendar.show_overlay(url);
        };

        // Hookup the fullcalendar
        foreachcalendar(function(cal) {
            var calendar = cal;

            var add = function(start, end, allDay) {
                eventAdd(start, end, allDay, calendar);  
            };

            var move = function(event) {
                moveEvent(event, calendar);
            };

            var render = function(event, element) {
                renderEvent(event, element, calendar);
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
                select: add,
                editable: true,
                eventAfterRender: render,
                eventResize: move,
                eventDrop: move
            };

            // Merge the options with the ones defined by the resource view
            $.extend(options, calendar.options);
            calendar.element.fullCalendar(options);
        });

        // Call all calendars with the given function and argument
        // the calendar from which the event originats is not called
        var all_calendars = function(originid, fn, arg) {
            for (var i=0; i<seantis.calendars.length; i++) {
                if (seantis.calendars[i].id === originid)
                    continue;
                
                $(seantis.calendars[i].id).fullCalendar( fn, arg );
            }  
        };

        // Generate the all calendars function
        var get_all_calendars_fn = function(originid, fn, arg) {
            var origin = originid;
            var func = fn;
            var argument = arg;
            return function() {
                all_calendars(origin, func, arg);  
            };
        };

        // Hook up the button synchronization
        foreachcalendar(function(calendar) {
            var id = calendar.id;
            var element = calendar.element;

            var prev = $('.fc-button-prev', element);
            var next = $('.fc-button-next', element);
            var month = $('.fc-button-month', element);
            var week = $('.fc-button-agendaWeek', element);
            var day = $('.fc-button-agendaDay', element);

            next.click(get_all_calendars_fn(id, 'next'));
            prev.click(get_all_calendars_fn(id, 'prev'));
            month.click(get_all_calendars_fn(id, 'changeView', 'month'));
            week.click(get_all_calendars_fn(id, 'changeView', 'agendaWeek'));
            day.click(get_all_calendars_fn(id, 'changeView', 'agendaDay'));
        });
    });
})( jQuery );