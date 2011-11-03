if (!this.seantis) this.seantis = {};
if (!this.seantis.calendars) this.seantis.calendars = [];

seantis.calendars.defaults = {
    timeFormat: 'HH:mm{ - HH:mm}',
    axisFormat: 'HH:mm{ - HH:mm}',
    columnFormat: 'dddd d.M',
    firstDay: 1,
};

(function($) {
    $(document).ready(function() {
        if (!seantis.calendars.length)
            return;

        seantis.calendars.init = function() {
            _.each(seantis.calendars, function(calendar, index) {
                calendar.element = $(calendar.id);
                calendar.index = index;
                calendar.groups = [];

                calendar.groups.add = function(group, element) {
                    if (_.isUndefined(group) || _.isEmpty(group))
                        return;

                    this.push({group:group, element:element});
                };

                calendar.groups.clear = function() {
                    this.length = 0;  
                };

                calendar.groups.find = function(group) {
                    var key = function(value) { return value.group == group; };
                    return _.pluck(_.filter(this, key), 'element');
                };

                // Sets a calendar event up with a form overlay
                calendar.overlay_init = function(element, onclose) {
                    var calendar = this;
                    element.prepOverlay({
                        subtype: 'ajax', 
                        filter:  common_content_filter,
                        formselector: 'form', 
                        noform: 'close',
                        afterpost: function(el) {
                            seantis.formgroups.init(el);
                        },
                        config: { 
                            onClose: function() {
                                calendar.is_resizing = false;
                                calendar.is_moving = false;
                                calendar.element.fullCalendar('refetchEvents');
                            },
                            onBeforeLoad: function() {
                                seantis.formgroups.init();
                            } 
                        } 
                    });
                };

                calendar.is_resizing = false;
                calendar.is_moving = false;

                // Shows the previously set form overlay
                calendar.overlay_show = function(url) {
                    var link = $('<a href="' + url + '"></a>');
                    this.overlay_init(link);
                    link.click();
                };

            });
        };

        var renderPartitions = function(event, element, calendar) {
            
            // if the event is being moved, don't render the partitions
            if (event.is_moving) {
                return;
            }

            var free = _.template('<div style="height:<%= height %>%"></div>');
            var used = _.template('<div style="height:<%= height %>%" class="calendarOccupied"></div>');

            var partitions = '';
            _.each(event.partitions, function(partition) {
                var reserved = partition[1];
                if (reserved === false) {
                    partitions += free({height: partition[0]});
                } else {
                    partitions += used({height: partition[0]});
                }
            });

            // lock the height during resizing
            var height = element.height();
            if (event.is_resizing) {
                height = _.isUndefined(event.height) ? height : event.height;
            } else {
                event.height = height;
            }

            partitions = '<div style="height:' + height + 'px;">' + partitions + '</div>';

            $('.fc-event-bg', element).wrapInner(partitions);
        };

        var renderEvent = function(event, element, calendar) {
            // Don't perform the following operations immediatly, but 
            // only once the ui thread is idle
            _.defer(function() {
                // Cache the element with the group for later usage
                calendar.groups.add(event.group, element);

                // Prepare the menu
                seantis.contextmenu(event, element, calendar);

                // Add partitions
                renderPartitions(event, element, calendar);

                // Init overlay for the click on the event
                calendar.overlay_init(element);
            });
        };

        // Called when an event is resized or moved
        var moveEvent = function(event, calendar) {
            var url = event.editurl;
            url += '&start=' + event.start.getTime() / 1000;
            url += '&end=' + event.end.getTime() / 1000;
            
            calendar.overlay_show(url);
        };

        // Called when a selection on the calendar is made
        var eventAdd = function(start, end, allDay, calendar) {
            if (!allDay) {
                var url = calendar.allocateurl;
                url += '?start=' + start.getTime() / 1000;
                url += '&end=' + end.getTime() / 1000;

                calendar.overlay_show(url);
            };
        };

        // Setup the supporting structure
        seantis.calendars.init();

        // Hookup the fullcalendar
        _.each(seantis.calendars, function(cal) {
            var calendar = cal;

            var add = function(start, end, allDay) {
                eventAdd(start, end, allDay, calendar);  
            };

            var move = function(event) {
                moveEvent(event, calendar);
            };

            var prerender = function(event, element) {
                calendar.groups.clear();
            };

            var render = function(event, element) {
                renderEvent(event, element, calendar);
            };

            var loading = function(loading, view) {
                calendar.groups.clear();
            };

            var highlight_group = function(event, highlight) {
                _.each(calendar.groups.find(event.group), function(el) {
                    el.toggleClass('groupSelection', highlight);  
                });
            }

            var mouseover = function(event) {
                highlight_group(event, true);
            };

            var mouseout = function(event) {
               highlight_group(event, false);
            }

            var options = {
                header: {
                    left: 'prev, next today',
                    right: 'month, agendaWeek, agendaDay'
                },
                defaultView: 'agendaWeek',
                allDaySlot: false,
                selectable: true,
                selectHelper: true,
                select: add,
                editable: true,
                eventRender: prerender,
                eventAfterRender: render,
                eventResize: move,
                eventDrop: move,
                isLoading: loading,
                eventMouseover: mouseover,
                eventMouseout: mouseout,
                //the following flags are never reset, because new event objects
                //are created if the resizing or dropping is successful
                eventResizeStart: function(event) { event.is_resizing = true; },
                eventDragStart: function(event) { event.is_moving = true; }
            };

            // Merge the options with the ones defined by the resource view as 
            // well as with the defaults
            $.extend(options, seantis.locale.fullcalendar());
            $.extend(options, seantis.calendars.defaults);
            $.extend(options, calendar.options);
            calendar.element.fullCalendar(options);
        });

        // Call all calendars with the given function and argument
        // the calendar from which the event originats is not called
        var all_calendars = function(originid, fn, arg) {
            _.each(seantis.calendars, function(calendar) {
                if (calendar.id !== originid)
                    calendar.element.fullCalendar(fn, arg); 
            });
        };

        // Generate the all calendars function
        var get_all_calendars_fn = function(originid, fn, arg) {
            return function() {
                all_calendars(originid, fn, arg);  
            };
        };

        // Hook up the button synchronization
        _.each(seantis.calendars, function(calendar) {
            var id = calendar.id;
            var element = calendar.element;

            var prev = $('.fc-button-prev', element);
            var next = $('.fc-button-next', element);
            var month = $('.fc-button-month', element);
            var week = $('.fc-button-agendaWeek', element);
            var day = $('.fc-button-agendaDay', element);
            var today = $('.fc-button-today', element);

            next.click(get_all_calendars_fn(id, 'next'));
            prev.click(get_all_calendars_fn(id, 'prev'));
            month.click(get_all_calendars_fn(id, 'changeView', 'month'));
            week.click(get_all_calendars_fn(id, 'changeView', 'agendaWeek'));
            day.click(get_all_calendars_fn(id, 'changeView', 'agendaDay'));
            today.click(get_all_calendars_fn(id, 'today'));
        });
    });
})( jQuery );