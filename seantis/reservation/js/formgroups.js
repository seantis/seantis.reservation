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
            field.toggle(show); 
        });
    };

    options.refresh = function() {
        options.show_fields(options.is_enabled());
    };

    var o = options;
    o.show_fields(o.is_enabled());
    o.trigger.change(function() {
        o.show_fields(o.is_enabled()); 
    });

    seantis.formgroups.groups[options.name] = options;
};

seantis.formgroups.clear = function() {
    seantis.formgroups.groups = {};  
};

seantis.formgroups.add_utility_links = function(findfn) {
    var find = findfn;

    var timeframes_field = find('#formfield-form-widgets-timeframes input');
    if (!timeframes_field.length)
        return;

    var timeframes = $.parseJSON(timeframes_field.val());
    timeframes = _.sortBy(timeframes, function(frame) {
        return frame.start;
    });
    
    var target = find('#formfield-form-widgets-recurrence_start');
    var link = _.template('<div id="<%= id %>"><a href="#">&gt;&gt; <%= title %></a></div>');

    var start = {};
    start.year = find('#form-widgets-recurrence_start-year');
    start.month = find('#form-widgets-recurrence_start-month');
    start.day = find('#form-widgets-recurrence_start-day');

    var end = {};
    end.year = find('#form-widgets-recurrence_end-year');
    end.month = find('#form-widgets-recurrence_end-month');
    end.day = find('#form-widgets-recurrence_end-day');

    var set_date = function(recurrence, date) {
        var date = seantis.utils.parse_date(date);
        recurrence.year.val(date.year);
        recurrence.month.val(date.month);
        recurrence.day.val(date.day);
    };

    start.set = function(date) { set_date(start, date); };
    end.set = function(date) { set_date(end, date); };

    _.each(timeframes, function(frame) {
        var id = _.uniqueId('timeframe');
        var el = $(link({id: id, title: frame.title}));
        
        target.before(el);
        
        var tool = find('#' + id);
        tool.click(function(e) {
            start.set(frame.start);
            end.set(frame.end);

            e.preventDefault();
        });
        seantis.formgroups.groups.recurrent.fields.push(tool);
    });

    if (timeframes.length) {
        target.before($('<br />'));
    }

    seantis.formgroups.groups.recurrent.refresh();
};

seantis.formgroups.init = function(el) {
    seantis.formgroups.clear();

    var root = _.isUndefined(el) ? null : $(el);
    var find = function(selector) { return $(selector, root); };
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
        name: "approve",
        trigger: find('#form-widgets-approve-0'),
        fields: [
            find('#formfield-form-widgets-waitinglist_spots')
        ]
    });

    seantis.formgroups.add_utility_links(find);
};

(function($) {
    $(document).ready(function() {
        seantis.formgroups.init();
    });
})( jQuery );