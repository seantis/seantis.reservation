if (!this.seantis) this.seantis = {};
if (!this.seantis.calendar) this.seantis.calender = {};
if (!this.seantis.overview) this.seantis.overview = {};

seantis.overview.days = {
    store: {},
    cleared: false,

    key: function(date) { 
        return date.getFullYear() + '-' + date.getMonth() + '-' + date.getDate();
    },   

    clear: function() {
        var cells = this.cells();
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
    },

    add: function(date, cell) {
        if (!this.cleared)
            this.cleared = this.clear();
            
        this.store[this.key(date)] = cell;
    },

    get: function(date) {
        return this.store[this.key(date)];
    },

    dates: function() { return _.keys(this.store); },
    cells: function() { return _.values(this.store); }
};

(function($) {
    $(document).ready(function() {
        
        if (_.isUndefined(seantis.overview.id))
            return;

        seantis.overview.element = $(seantis.overview.id);

        seantis.overview.items = function(uuids) {
            var uuidmap = seantis.overview.options.uuidmap;
            if (_.isEmpty(uuids) || _.isEmpty(uuidmap))
                return [];

            return _.unique(_.map(uuids, function(uuid) {
               return uuidmap[uuid]; 
            }));
        };

        seantis.overview.render = function(event, element) {
            var cell = seantis.overview.days.get(event.start);
            if (!_.isUndefined(cell) && ! cell.data('old_classes')) {
                var items = seantis.overview.items(event.uuids);
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

        seantis.overview.resultmouseover = function() {
            var element = $('.' + $(this).attr('id'));
            highlight_group(element, true);
        };

        seantis.overview.resultmouseout = function() {
            var element = $('.' + $(this).attr('id'));
            highlight_group(element, false);
        };  

        var dayrender = function(date, element, view) {
            seantis.overview.days.add(date, element);
        };

        var isloading = function() {
            seantis.overview.days.cleared = false;
        };

        $('.directoryResult').mouseenter(seantis.overview.resultmouseover);
        $('.directoryResult').mouseleave(seantis.overview.resultmouseout);
        
        var options = {
            firstDay: 1,
            timeFormat: 'HH:mm{ - HH:mm}',
            axisFormat: 'HH:mm{ - HH:mm}',
            columnFormat: 'ddd d.M',
            eventRender: seantis.overview.render,
            dayRender: dayrender,
            loading: isloading
        };

        $.extend(options, seantis.locale.fullcalendar());
        $.extend(options, seantis.overview.options);
        seantis.overview.element.fullCalendar(options);
    });
})( jQuery );