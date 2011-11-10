var CalendarDays = function (options) {
    var cleared = false;
    var store = {};
    var get_dates =  function() { return _.keys(store); };
    var get_cells =  function() { return _.values(store); };
    var key = function(date) {
        return date.getFullYear() + '-' + date.getMonth() + '-' + date.getDate();
    };

    var clear = function() {
        var cells = get_cells();
        for(var i=0; i<cells.length; i++) {
            var cell = cells[i];

            var old_classes = cell.data('old_classes');
            if (old_classes) {
                cell.removeClass(old_classes);
                cell.removeData('old_classes');
            }

            cell.unbind('mouseenter');
            cell.unbind('mouseleave');
        }

        return true;
    };

    var add = function(date, cell) {
        if (!cleared)
            cleared = clear();
            
        store[key(date)] = cell;
    };

    var get = function(date) { 
        return store[key(date)]; 
    };

    this.add = add;
    this.get = get;

    options.loading = function() { 
        cleared=false; 
    };
    options.dayRender = function(date, element) { add(date, element); };
};

(function($) {
    $(document).ready(function() {

        if (_.isUndefined(seantis.overview.id))
            return;

        var overview = $(seantis.overview.id);

        var options = {};
        var days = new CalendarDays(options);

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
            if (!_.isUndefined(cell) && ! cell.data('old_classes')) {
                var items = get_items(event.uuids);
                var itemids = '#' + items.join(', #');
                var classes = event.className.join(' ') + ' ' + items.join(' ');

                cell.addClass(classes);
                cell.data('old_classes', classes); 
                
                cell.bind('mouseenter', function() {
                    highlight_group($(itemids), true);
                    highlight_group($(cell), true);
                });
                
                cell.bind('mouseleave', function() {
                    highlight_group($(itemids), false);
                    highlight_group($(cell), false);
                });
            }

            return false;
        };

        var highlight_group = function(elements, highlight) {
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

        var dayrender = function(date, element, view) {
            days.add(date, element);
        };

        var isloading = function() {
            days.cleared = false;
        };

        $('.directoryResult').mouseenter(item_mouseover);
        $('.directoryResult').mouseleave(item_mouseout);
        
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