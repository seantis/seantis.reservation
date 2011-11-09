if (!this.seantis) this.seantis = {};
if (!this.seantis.overview) this.seantis.overview = {};

(function($) {
    $(document).ready(function() {
        if (_.isUndefined(seantis.overview.id))
            return;

        seantis.overview.element = $(seantis.overview.id);
        seantis.overview.days = {};

        seantis.overview.items = function(uuids) {
            var uuidmap = seantis.overview.options.uuidmap;
            if (_.isEmpty(uuids) || _.isEmpty(uuidmap))
                return [];

            return _.unique(_.map(uuids, function(uuid) {
               return uuidmap[uuid]; 
            }));
        };

        seantis.overview.render = function(event, element) {
            var cell = seantis.overview.dayelement(event.start);
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

        seantis.overview.datekey = function(date) {
            var key = date.getFullYear().toString() + '-';
            key += date.getMonth().toString() + '-';
            key += date.getDate().toString();
            return key;
        }

        seantis.overview.dayelement = function(date) {
            return seantis.overview.days[seantis.overview.datekey(date)];
        };

        seantis.overview.dayrender = function(date, element, view) {
            if (!seantis.overview.days.cleared) {
                var keys = _.keys(seantis.overview.days);
                for(var i=0; i<keys.length; i++) {
                    var key = keys[i];
                    var el = seantis.overview.days[key];
                    
                    if (!el.data)
                        continue;

                    var old_classes = el.data('old_classes');
                    if (old_classes) {
                        el.removeClass(old_classes);
                        el.removeData('old_classes');
                    }
                }

                _.each(_.values(seantis.overview.days), function(cell) {
                    if (!_.isUndefined(cell.unbind)) {
                        cell.unbind('mouseenter');
                        cell.unbind('mouseleave');
                    } 
                });

                seantis.overview.days = {};
                seantis.overview.days.cleared = true;
            }

            var key = seantis.overview.datekey(date);
            seantis.overview.days[seantis.overview.datekey(date)] = element;
        };

        $('.directoryResult').mouseenter(seantis.overview.resultmouseover);
        $('.directoryResult').mouseleave(seantis.overview.resultmouseout);
        
        var options = {
            firstDay: 1,
            timeFormat: 'HH:mm{ - HH:mm}',
            axisFormat: 'HH:mm{ - HH:mm}',
            columnFormat: 'ddd d.M',
            eventRender: seantis.overview.render,
            dayRender: seantis.overview.dayrender,
            loading: function(isLoading, view) { seantis.overview.days.cleared = false; }
        };

        $.extend(options, seantis.locale.fullcalendar());
        $.extend(options, seantis.overview.options);
        seantis.overview.element.fullCalendar(options);
    });
})( jQuery );