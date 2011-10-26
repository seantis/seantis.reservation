if (!this.seantis) this.seantis = {};
if (!this.seantis.formgroups) this.seantis.formgroups = {};

var RRULE_DAILY = 3;
seantis.formgroups.groups = {};

seantis.formgroups.add = function(options) {
    var $ = jQuery;

    options.is_enabled = function() {
        if (options.on_is_enabled) return options.on_is_enabled(options.trigger);

        return options.trigger.is(':checked');
    };

    options.show_fields = function(show) {
        if (options.on_show) options.on_show(show);

        _.each(options.fields, function(field) {
            field.toggle(show); 
        });
    };

    var o = options;
    o.show_fields(o.is_enabled());
    o.trigger.change(function() {
        o.show_fields(o.is_enabled()); 
    });

    seantis.formgroups.groups[options.name] = options;
};

seantis.formgroups.init = function() {
    
    var groups = seantis.formgroups.groups;

    this.add({
        name: "recurring",
        trigger: $('#form-widgets-recurring-0'),
        fields: [
            $('#formfield-form-widgets-frequency'),
            $('#formfield-form-widgets-recurrence_end')
        ],
        on_show: function(show) {
            if (groups.days)
                groups.days.trigger.change();
        }
    });

    this.add({
        name: "partly",
        trigger: $('#form-widgets-partly_available-0'),
        fields: [
            $('#formfield-form-widgets-raster')
        ]
    });

    var days = this.add({
       name: "days",
       trigger: $('#form-widgets-frequency'),
       fields: [
            $('#formfield-form-widgets-days')
       ],
       on_is_enabled: function(trigger) {
            if (!groups.recurring.is_enabled())
                return false;
            
            return trigger.val() == RRULE_DAILY;
       }
    });
};

(function($) {
    $(document).ready(function() {
        seantis.formgroups.init();
    });
})( jQuery );