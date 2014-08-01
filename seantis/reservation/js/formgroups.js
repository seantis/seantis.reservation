if (!this.seantis) this.seantis = {};
if (!this.seantis.formgroups) this.seantis.formgroups = {};

seantis.formgroups.groups = {};

seantis.formgroups.add = function(options) {
    var $ = jQuery;

    options.is_enabled = function() {
        if (options.on_is_enabled) return options.on_is_enabled(options.trigger);

        return options.trigger.is(':checked');
    };

    options.show_fields = function(show, no_notify) {
        if (!no_notify && options.on_show) options.on_show(show);

        _.each(options.fields, function(field) {
            // toggle does animations for some weird reason
            if (show) {
                field.show();
            } else {
                field.hide();
            }
        });
    };

    options.refresh = function() {
        options.show_fields(options.is_enabled());
    };

    var on_trigger = function() {
        o.show_fields(o.is_enabled());
    };

    var o = options;
    o.show_fields(o.is_enabled());
    o.trigger.change(on_trigger);

    if (! _.isUndefined(o.other_triggers)) {
        o.other_triggers.change(on_trigger);
    }

    seantis.formgroups.groups[options.name] = options;
};

seantis.formgroups.clear = function() {
    seantis.formgroups.groups = {};
};

seantis.formgroups.get_date = function(field) {
    var find = seantis.formgroups.find;

    var valid_fields = ['recurrence_start', 'recurrence_end'];
    _.assert(_.contains(valid_fields, field), 'invalid field: ' + field);

    var date = {};
    date.year = find('#form-widgets-' + field + '-year').val();
    date.month = find('#form-widgets-' + field + '-month').val();
    date.day = find('#form-widgets-' + field + '-day').val();

    if (_.contains([date.year, date.month, date.day], undefined)) {
        return null;
    }

    date.year = parseInt(date.year, 10);
    date.month = parseInt(date.month, 10);
    date.day = parseInt(date.day, 10);

    return new Date(date.year, date.month - 1, date.day);
};

seantis.formgroups.set_date = function(field, date) {
    var find = seantis.formgroups.find;

    var valid_fields = ['recurrence_start', 'recurrence_end'];
    _.assert(_.contains(valid_fields, field), 'invalid field: ' + field);

    find('#form-widgets-' + field + '-year').val(date.year);
    find('#form-widgets-' + field + '-month').val(date.month);
    find('#form-widgets-' + field + '-day').val(date.day);
};

seantis.formgroups.add_utility_links = function() {
    var find = seantis.formgroups.find;

    var timeframes_field = find('#formfield-form-widgets-timeframes input');

    if (!timeframes_field.length)
        return;

    var timeframes = $.parseJSON(timeframes_field.val());
    timeframes = _.sortBy(timeframes, function(frame) {
        return frame.start;
    });

    if (!timeframes.length)
        return;

    var targets = find([
        '#formfield-form-widgets-recurrence_start',
        '#formfield-form-widgets-recurrence_end'
    ].join(', '));

    var link = _.template('<div id="<%= id %>"><a href="#"><%= title %></a></div>');

    var start = seantis.formgroups.get_date('recurrence_start');
    var end = seantis.formgroups.get_date('recurrence_end');

    var content = [];

    _.each(timeframes, function(frame) {
        var id = _.uniqueId('timeframe');

        content.push(
            link({id: id, title: frame.title.replace(/ /g, '&nbsp;')})
        );
    });

    var render_menu = function(element) {
        var links = _.map($(element).find('a'), $);
        _.each(links, function(link, ix) {
            link.click(function(e) {
                seantis.formgroups.set_date(
                    'recurrence_start', _.parse_date(timeframes[ix].start)
                );
                seantis.formgroups.set_date(
                    'recurrence_end', _.parse_date(timeframes[ix].end)
                );

                seantis.formgroups.autoselect_days();

                $.fn.miniTip({doHide:true});

                e.preventDefault();
            });
        });
    };

    _.defer(function() {
        targets.append('<a href="#" class="timeframes-trigger"></a>');
        targets.find('a.timeframes-trigger').miniTip({
            title: '',
            content: content.join('\n'),
            anchor: 'e',
            delay: 0,
            event: 'click',
            aHide: true,
            fadeIn: 100,
            fadeOut: 100,
            maxW: '333px',
            render: render_menu
        });
    });
};

seantis.formgroups.autoselect_days = function() {
    "use strict";

    var find = seantis.formgroups.find;
    var start = seantis.formgroups.get_date('recurrence_start');
    var end = seantis.formgroups.get_date('recurrence_end');

    if (_.contains([start, end], null)) {
        return;
    }

    if (start > end) {
        return;
    }

    var ids = _.map([6, 0, 1, 2, 3, 4, 5],
        function(ix) {
            return '#form-widgets-days-' + ix;
        }
    );

    var days = _.map(ids, find);

    var span = ((end - start) / 1000 / 60 / 60 / 24) + 1;
    var first = start.getDay();
    var last = end.getDay();

    var checked = [];
    var i = 0;

    if (span >= 7) {
        checked = [0, 1, 2, 3, 4, 5, 6];
    } else if (first == last) {
        checked = [first];
    } else if (first < last) {
        for (i=first; i<=last; i++) {
            checked.push(i);
        }
    } else {
        for (i=0; i<= last; i++) {
            checked.push(i);
        }
        for (i=6; i>= first; i--) {
            checked.push(i);
        }
    }

    _.each(days, function(day) {
        day.removeAttr('checked');
    });

    _.each(checked, function(ix) {
        days[ix].attr('checked', 'checked');
    });
};

seantis.formgroups.add_recurrency_helper = function() {
    "use strict";

    var ids = [
        '#formfield-form-widgets-recurrence_start',
        '#formfield-form-widgets-recurrence_end'
    ];

    $(ids.join(', ')).change(function() {
        _.defer(seantis.formgroups.autoselect_days);
    });
};

seantis.formgroups.init = function(el) {
    seantis.formgroups.clear();

    var root = _.isUndefined(el) ? null : $(el);
    var find = function(selector) { return $(selector, root); };

    seantis.formgroups.find = find;

    var groups = seantis.formgroups.groups;
    var add = seantis.formgroups.add;

    add({
        name: "once",
        trigger: find('#form-widgets-recurring-0'),
        fields: [
            find('#formfield-form-widgets-day')
        ],
        on_is_enabled: function(trigger) {
            return trigger.attr('checked');
        },
        on_show: function(show) {
            if (groups.recurrent)
                groups.recurrent.show_fields(!show, true);
        }
    });

    add({
        name: "recurrent",
        trigger: find('#form-widgets-recurring-1'),
        fields: [
            find('#formfield-form-widgets-recurrence_start'),
            find('#formfield-form-widgets-recurrence_end'),
            find('#formfield-form-widgets-days'),
            find('#formfield-form-widgets-separately')
        ],
        on_is_enabled: function(trigger) {
            if ($(document).find('.always-show-days').length) {
                return true;
            }
            return trigger.attr('checked');
        },
        on_show: function(show) {
            if (groups.once)
                groups.once.show_fields(!show, true);
        }
    });

    add({
        name: "partly",
        trigger: find('#form-widgets-partly_available-0'),
        fields: [
            find('#formfield-form-widgets-raster')
        ]
    });

    add({
        name: "selected_date",
        trigger: find('#form-widgets-selected_date-1'),
        fields: [
            find('#formfield-form-widgets-specific_date')
        ],
        other_triggers: find('#form-widgets-selected_date-0')
    });

    add({
        name: "whole_day",
        trigger: find('#form-widgets-whole_day-0'),
        fields: [
            find('#formfield-form-widgets-start_time'),
            find('#formfield-form-widgets-end_time')
        ],
        on_is_enabled: function(trigger) {
            return ! trigger.is(':checked');
        }
    });

    add({
        name: "send_email",
        trigger: find('#form-widgets-send_email-0'),
        fields: [
            find('#formfield-form-widgets-reason')
        ],
        on_is_enabled: function(trigger) {
            return trigger.is(':checked');
        }
    });

    add({
        name: "send_email_to_managers",
        trigger: find('#form-widgets-send_email_to_managers-2'),
        fields: [
            find('#formfield-form-widgets-manager_email')
        ],
        on_is_enabled: function(trigger) {
            return trigger.is(':checked');
        },
        other_triggers: find(
            [
                '#form-widgets-send_email_to_managers-0',
                '#form-widgets-send_email_to_managers-1'
            ].join(',')
        )
    });

    seantis.formgroups.add_utility_links();
    seantis.formgroups.add_recurrency_helper();

    // don't autoselect days on load, if a specific id exists
    if ($(document).find('#autoselect-days-on-load').length === 0) {
        seantis.formgroups.autoselect_days();
    }
};

(function($) {
    $(document).ready(function() {
        seantis.formgroups.init();
    });
})( jQuery );