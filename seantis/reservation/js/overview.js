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
                var classes = event.className.join(' ');
                classes += ' ' + seantis.overview.items(event.uuids).join(' ');

                cell.addClass(classes);
                cell.data('old_classes', classes); 
                
                cell.mouseenter(function() {
                    seantis.overview.mouseover(event, cell);
                });
                cell.mouseleave(function() {
                    seantis.overview.mouseout(event, cell);
                });
            }

            return false;
        };

        var highlight_group = function(elements, highlight) {
            elements.toggleClass('groupSelection', highlight);
        };

        seantis.overview.mouseover = function(event, cell) {
            var ids = '#' + seantis.overview.items(event.uuids).join(', #');
            highlight_group($(ids), true);
            highlight_group($(cell), true);
        };

        seantis.overview.mouseout = function(event, cell) {
            var ids = '#' + seantis.overview.items(event.uuids).join(', #');
            highlight_group($(ids), false);
            highlight_group($(cell), false);
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
                console.log('removing old classes');
                seantis.overview.days.cleared = true;

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
                console.log('finished removing old classes');
            }

            var key = seantis.overview.datekey(date);
            if (_.isUndefined(seantis.overview.days[key]))
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