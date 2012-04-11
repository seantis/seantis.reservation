/*
    CalendarDays helps managing the different day cells on a fullcalendar grid.
    It is initialized like so:

    days = new CalendarDays(options);

    The options paramter is an option object meant to be passed to fullcalendar
    1.6+ which offers the dayrender callback
*/
var CalendarDays = function (options) {

    // Object to store the dates and the corresponding cell element
    var store = {};

    // Indicates that the store needs clearing (see clear)
    var cleared = false;

    // Returns all the cells in the store
    var cells =  function() { return _.values(store); };

    // Key function with which a date is stored
    var key = function(date) { return date.toDateString(); };

    // Fullcalendar only creates the cells once, so in order for them to be
    // be used differently in for each datereange they need to be cleared
    // after the loading callback of the fullcalendar has been fired
    // As dayRender is fired before loading, the clearing is actually
    // done once before dayRender is called again
    var clear = function() {
        _.each(cells(), function(cell) {
            var old_classes = cell.data('old_classes');
            if (old_classes) {
                cell.removeClass(old_classes);
                cell.removeData('old_classes');
            }

            cell.unbind('mouseenter.days');
            cell.unbind('mouseleave.days');    
        });
        
        return true;
    };

    // Add a cell to the store. Clearing is done once first, if needed
    var add = function(date, cell) {
        if (!cleared) 
            cleared = clear();
            
        store[key(date)] = cell;
    };

    var get = function(date) { 
        return store[key(date)]; 
    };

    //Make these functions public
    this.add = add;
    this.get = get;

    //Adds a class to a date cell and stores the result for later cleaning
    this.addClass = function(date, classes) {
        var cell = get(date);
        cell.addClass(classes);
        cell.data('old_classes', classes); 
    };

    this.mouseenter = function(date, callback) {
        var cell = get(date);
        cell.bind('mouseenter.days', callback);
    };

    this.mouseleave = function(date, callback) {
        var cell = get(date);
        cell.bind('mouseleave.days', callback);
    };

    options.loading = function() { 
        cleared=false; //indicate that the next add call has to clear the store
    };

    options.dayRender = function(date, element) { 
        add(date, element); 
    };
};

(function($) {
    $(document).ready(function() {

        if (_.isUndefined(seantis.overview))
            return;

        if (_.isUndefined(seantis.overview.id))
            return;

        var overview = $(seantis.overview.id);

        var get_items = function(uuids) {
            var uuidmap = options.uuidmap;
            if (_.isEmpty(uuids) || _.isEmpty(uuidmap))
                return [];

            return _.unique(_.map(uuids, function(uuid) {
               return uuidmap[uuid]; 
            }));
        };

        var render = function(event, element) {
            var cell = days.get(event.start);
            if (!_.isUndefined(cell)) {
                var items = get_items(event.uuids);
                var itemids = '#' + items.join(', #');
                var itemuuids = '#' + event.uuids.join(', #');
                var classes = event.className.join(' ') + ' ' + items.join(' ') + ' ' + event.uuids.join(' ');

                days.addClass(event.start, classes);
                days.mouseenter(event.start, function() {
                    _.defer(function() {
                        highlight_group($(itemids), true);
                        highlight_group($(itemuuids), true);
                        highlight_group($(cell), true);    
                    });
                });
                
                days.mouseleave(event.start, function() {
                    _.defer(function() {
                        highlight_group($(itemids), false);
                        highlight_group($(itemuuids), false);
                        highlight_group($(cell), false);
                    });
                });   
            }

            return false;
        };

        var highlight_group = function(elements, highlight) {
            console.log('highlight: ' + highlight);
            elements.toggleClass('groupSelection', highlight);    
        };

        var item_mouseover = function() {
            var element = $('.' + $(this).attr('id'));
            highlight_group(element, true);
        };

        var item_mouseout = function() {
            var element = $('.' + $(this).attr('id'));
            highlight_group(element, false);
        };

        var directoryResult = $('.directoryResult, .resourceItem');
        directoryResult.mouseenter(function() {
            var element = $('.' + $(this).attr('id'));
            highlight_group(element, true);
        });

        directoryResult.mouseleave(function() {
            var element = $('.' + $(this).attr('id'));
            highlight_group(element, false);
        });
        
        var options = {};
        var days = new CalendarDays(options);

        $.extend(options, {
            firstDay: 1,
            timeFormat: 'HH:mm{ - HH:mm}',
            axisFormat: 'HH:mm{ - HH:mm}',
            columnFormat: 'ddd d.M',
            eventRender: render
        });
        $.extend(options, seantis.locale.fullcalendar());
        $.extend(options, seantis.overview.options);

        overview.fullCalendar(options);
    });
})( jQuery );