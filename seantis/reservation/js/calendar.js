if (!this.seantis) this.seantis = {};
if (!this.seantis.calendars) this.seantis.calendars = [];

(function($) {
    $(document).ready(function() {
        if (!seantis || !seantis.calendars.length)
            return;

        // Adds a plone overlay to a form view.
        // Submitting the form will force the calendar to refetch the events
        for(var i=0; i< seantis.calendars.length; i++) {
            var calendarindex = i;
            seantis.calendars[calendarindex].form_overlay = function(element) {
                element.prepOverlay({
                    subtype: 'ajax',
                    filter: '#content>*',
                    formselector: 'form',
                    noform: 'close',
                    config: {
                        onClose: function() {
                            var calendarid = seantis.calendars[calendarindex].id;
                            $(calendarid).fullCalendar('refetchEvents');    
                        }
                    }
                });
            };
        }

        var show_overlay = function(url, calendarindex) {
            var link = $('<a href="' + url + '"></a>');
            seantis.calendars[calendarindex].form_overlay(link);
            link.click();
        };

        // Prepares the contextmenu for the event and adds the form overlay
        var renderEvent = function(event, element, calendarindex) {
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

            seantis.contextmenu(element, menuhtml, calendarindex);
            seantis.calendars[calendarindex].form_overlay(element);

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

        var moveEvent = function(event, calendarindex) {
            var url = event.editurl;
            url += '&start=' + event.start.getTime() / 1000;
            url += '&end=' + event.end.getTime() / 1000;
            
            show_overlay(url, calendarindex);
        };

        // Called when a selection on the calendar is made
        // TODO do not execute if the permissions are insufficient
        var eventAdd = function(start, end, allDay, calendarindex) {
            if (allDay) return;

            var url = seantis.calendars[calendarindex].allocateurl;
            url += '?start=' + start.getTime() / 1000;
            url += '&end=' + end.getTime() / 1000;

            show_overlay(url, calendarindex);
        };

        for (var i=0; i<seantis.calendars.length; i++) {
            var calendarindex = i;

            var add = function(start, end, allDay) {
                eventAdd(start, end, allDay, calendarindex);  
            };

            var move = function(event) {
                moveEvent(event, calendarindex);
            };

            var render = function(event, element) {
                renderEvent(event, element, calendarindex);
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
                eventDrop: move,
                viewDisplay: function(view) {
                    console.log(view);
                }
            };

            // Merge the options with the ones defined by the resource view
            $.extend(options, seantis.calendars[i].options);
            $(seantis.calendars[i].id).fullCalendar(options);
        }

        var all_calendars = function(originid, fn, arg) {
            for (var i=0; i<seantis.calendars.length; i++) {
                if (seantis.calendars[i].id === originid)
                    continue;
                
                $(seantis.calendars[i].id).fullCalendar( fn, arg );
            }  
        };

        var get_all_calendars_fn = function(originid, fn, arg) {
            var origin = originid;
            var func = fn;
            var argument = arg;
            return function() {
                all_calendars(origin, func, arg);  
            };
        };

        // Hook up the button synchronization
        for (var i=0; i<seantis.calendars.length; i++) {
            var calendarid = seantis.calendars[i].id;

            var calendar = $(calendarid);

            var prev = $('.fc-button-prev', calendar);
            var next = $('.fc-button-next', calendar);
            var month = $('.fc-button-month', calendar);
            var week = $('.fc-button-agendaWeek', calendar);
            var day = $('.fc-button-agendaDay', calendar);

            'month, agendaWeek, agendaDay'

            next.click(get_all_calendars_fn(calendarid, 'next'));
            prev.click(get_all_calendars_fn(calendarid, 'prev'));
            month.click(get_all_calendars_fn(calendarid, 'changeView', 'month'));
            week.click(get_all_calendars_fn(calendarid, 'changeView', 'agendaWeek'));
            day.click(get_all_calendars_fn(calendarid, 'changeView', 'agendaDay'));
        }
    });
})( jQuery );