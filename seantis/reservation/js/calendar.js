if (!this.seantis) this.seantis = {};
if (!this.seantis.calendars) this.seantis.calendars = [];

seantis.calendars.defaults = {
    timeFormat: 'HH:mm{ - HH:mm}',
    axisFormat: 'HH:mm{ - HH:mm}',
    columnFormat: {
        month: 'dddd',    // Mon
        week: 'ddd d.M', // Mon 7.9
        day: 'dddd d.M'  // Monday 7.9
    },
    firstDay: 1
};

// Keeps a list of event elements and the event group to which they belong to
var CalendarGroups = function() {
    var groups = [];

    // add a group and its element
    this.add = function(group, element) {
        if (_.isUndefined(group) || _.isEmpty(group))
            return;

        groups.push({group:group, element:element});
    };

    // filter the list by the given group returning the elements of the result
    this.find = function(group) {
        var key = function(value) { return value.group == group; };
        return _.pluck(_.filter(groups, key), 'element');
    };

    // empty the list
    this.clear = function() {
        groups.length = 0;  
    };
};

(function($) {
    $(document).ready(function() {

        // only run if there are any calendars
        if (!seantis.calendars.length) return;

        // initializes all calendars on the site
        var init = function() {
            _.each(seantis.calendars, function(calendar, index) {
                
                calendar.element = $(calendar.id);
                calendar.index = index;
                calendar.groups = new CalendarGroups();
                
                //indicate that the calendar an event is being resized or moved
                calendar.is_resizing = false;
                calendar.is_moving = false;
                
                // refetch the calendar events
                calendar.refetch = function() { 
                    calendar.element.fullCalendar('refetchEvents');
                };

                // Sets an element on the calendar up with an overlay
                calendar.overlay_init = function(element, onclose) {
                    var on_close = function() {
                        calendar.is_resizing = false;
                        calendar.is_moving = false;
                        calendar.refetch();

                        if (onclose) _.defer(onclose);
                    };

                    var before_load = function() {
                        seantis.formgroups.init();
                        seantis.contextmenu.close();
                    };

                    var after_post = function(el) {
                        seantis.formgroups.init(el);
                    };

                    element.prepOverlay({
                        subtype: 'ajax', 
                        filter:  common_content_filter,
                        formselector: 'form', 
                        closeselector: '[name=form.buttons.cancel]',
                        noform: 'close',
                        afterpost: after_post,
                        config: { 
                            onClose: on_close, 
                            onBeforeLoad: before_load
                        }
                    });
                };

                // Sets a an element on the calendar up with an inline load
                calendar.inline_init = function(element, url, filter, target) {

                    //fetches the requested url
                    var fetch = function() {
                        // show loading gif
                        target.toggleClass('loading', true);

                        // load the page
                        $.get(url, function(data) {
                            var result = $(filter, $(data));

                            // add a close button in front of the result
                            var close = '<div id="inlineClose"></div>\
                                         <div style="clear:both;"></div>';

                            target.html(close + result.html());

                            // hookup the close button
                            target.find('#inlineClose').click(function() {
                               target.html(''); 
                            });

                            // setup all links with overlays, refetching
                            // the loaded page once the overlay is closed
                            $.each($('a', target), function(ix, link) {

                                // use the calendar overlay so the calendar
                                // is reloaded as well
                                calendar.overlay_init($(link), function() {
                                    fetch();
                                }); 

                            });

                            // if there are data-group elements hook them up
                            // with the highlighting
                            var groups = target.find('div[data-group]');
                            
                            groups.mouseenter(function() {
                                console.log('hit');
                                var group = $(this).attr('data-group');
                                if (!_.isEmpty(group))
                                    calendar.highlight_group(group, true);
                            });

                            groups.mouseleave(function() {
                                var group = $(this).attr('data-group');
                                if (!_.isEmpty(group))
                                    calendar.highlight_group(group, false);
                            })

                            // hide loading gif
                            target.toggleClass('loading', false);
                        });
                    };

                    element.click(function(event) {
                        fetch();
                        seantis.contextmenu.close();
                        event.preventDefault();
                    });
                };

                calendar.highlight_group = function(group, highlight) {
                    _.each(calendar.groups.find(group), function(el) {
                        el.toggleClass('groupSelection', highlight);  
                    });
                };

                // initializes and then shows the overlay
                calendar.overlay_show = function(url) {
                    var link = $('<a href="' + url + '"></a>');
                    this.overlay_init(link);
                    link.click();
                };

            });
        }(); // run init immediatly

        // renders the occupied partitions on an event
        var render_partitions = function(event, element, calendar) {
            
            // if the event is being moved, don't render the partitions
            if (event.is_moving) {
                return;
            }

            var free = _.template('<div style="height:<%= height %>"></div>');
            var used = _.template('<div style="height:<%= height %>" class="calendar-occupied"></div>');
            var partition_block = _.template('<div style="height:<%= height %>" <%= partitions %></div>');

            // build the individual partitions
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

            // render the whole block
            var html = partition_block({height:height, partitions:partitions});
            $('.fc-event-bg', element).wrapInner(html);
        };

        var render_event = function(event, element, calendar) {
            // Don't perform the following operations immediatly, but 
            // only once the ui thread is idle
            _.defer(function() {
                // Cache the element with the group for later usage
                calendar.groups.add(event.group, element);

                // Prepare the menu
                seantis.contextmenu(event, element, calendar);

                // Add partitions
                render_partitions(event, element, calendar);

                // Init overlay for the click on the event
                if (seantis.contextmenu.simple(event))
                    calendar.overlay_init(element);
            });
        };

        // move an event
        var move_event = function(event, calendar) {
            var url = event.moveurl;
            url += '&start=' + event.start.getTime() / 1000;
            url += '&end=' + event.end.getTime() / 1000;
            
            calendar.overlay_show(url);
        };

        // add an event made by a selection
        var add_event = function(start, end, allDay, calendar) {
            if (!allDay) {
                var url = calendar.addurl;
                url += '?start=' + start.getTime() / 1000;
                url += '&end=' + end.getTime() / 1000;

                calendar.overlay_show(url);
            }
        };

        // Hookup the fullcalendar
        _.each(seantis.calendars, function(cal) {
            var calendar = cal;

            var add = function(start, end, allDay) {
                add_event(start, end, allDay, calendar);  
            };

            var move = function(event) {
                move_event(event, calendar);
            };

            var prerender = function(event, element) {
                calendar.groups.clear();
            };

            var render = function(event, element) {
                render_event(event, element, calendar);
            };

            var loading = function(loading, view) {
                calendar.groups.clear();
            };

            var mouseover = function(event) {
                calendar.highlight_group(event.group, true);
            };

            var mouseout = function(event) {
                calendar.highlight_group(event.group, false);
            };

            var options = {
                header: {
                    left: 'prev, next today',
                    right: 'month, agendaWeek, agendaDay'
                },
                defaultView: 'agendaWeek',
                allDaySlot: false,
                selectHelper: true,
                select: add,
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
                if (calendar.id !== originid) {
                    calendar.element.fullCalendar(fn, arg); 
                }
            });
        };

        // same as all_calendars but for scrolling
        var scroll_calendars = function(originid, top, left) {
            _.each(seantis.calendars, function(calendar) {
                if (calendar.id !== originid) {
                    var block = $('div > div > div > div', calendar.element);
                    block.scrollTop(top)
                    block.scrollLeft(left);
                } 
            });
        };

        if (seantis.calendars.length) {

            var synced_buttons = {
                '.fc-button-prev':['prev'],
                '.fc-button-next':['next'],
                '.fc-button-month':['changeView', 'month'],
                '.fc-button-agendaWeek':['changeView', 'agendaWeek'],
                '.fc-button-agendaDay':['changeView', 'agendaDay'],
                '.fc-button-today':['today']
            };

            _.each(seantis.calendars, function(calendar) {
                var id = calendar.id;
                var element = calendar.element;

                //sync buttons
                _.each(_.keys(synced_buttons), function(button, ix) {
                    var fn = synced_buttons[button][0];
                    var arg = synced_buttons[button][1];
                    
                    $(button, element).click(function() {
                        all_calendars(id, fn, arg); 
                    }); 
                });

                //sync scrolling

                //the actual block with the overflow has no identity or class
                //so there's no other way but to rely on the hierarchy
                var block = $('div > div > div > div', calendar.element);
                
                block.scroll(function() {
                    scroll_calendars(id, block.scrollTop(), block.scrollLeft()); 
                });

            });
        } // end of calendars sync
    }); // end of jquery ready
})( jQuery );