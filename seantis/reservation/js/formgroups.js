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

    var target = find('#formfield-form-widgets-recurrence_start');
    var link = _.template('<div id="<%= id %>"><a href="#">&gt;&gt; <%= title %></a></div>');

    var start = seantis.formgroups.get_date('recurrence_start');
    var end = seantis.formgroups.get_date('recurrence_end');

    _.each(timeframes, function(frame) {
        var id = _.uniqueId('timeframe');
        var el = $(link({id: id, title: frame.title}));

        target.before(el);

        var tool = find('#' + id);
        tool.click(function(e) {

            seantis.formgroups.set_date(
                'recurrence_start', _.parse_date(frame.start)
            );
            seantis.formgroups.set_date(
                'recurrence_end', _.parse_date(frame.end)
            );

            // seantis.formgroups.autoselect_days();

            e.preventDefault();
        });
        seantis.formgroups.groups.recurrence.fields.push(tool);
    });

    if (timeframes.length) {
        target.before($('<br />'));
    }
};

seantis.formgroups.init = function(el) {
    seantis.formgroups.clear();

    var root = _.isUndefined(el) ? null : $(el);
    var find = function(selector) { return $(selector, root); };

    seantis.formgroups.find = find;

    var groups = seantis.formgroups.groups;
    var add = seantis.formgroups.add;

    add({
        name: "recurrence",
        trigger: find("#form-widgets-recurrence"),
        fields: [
            find('#formfield-form-widgets-separately')
        ],
        on_is_enabled: function(trigger) {
            return trigger.val() !== undefined && trigger.val() !== '';
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

    seantis.formgroups.add_utility_links();
};

(function($) {
    $(document).ready(function() {
        seantis.formgroups.init();
    });
})( jQuery );
