if (!this.seantis) this.seantis = {};
if (!this.seantis.formgroups) this.seantis.formgroups = {};

seantis.formgroups.add = function(options) {
    var $ = jQuery;

    var is_enabled = function() {
        if (!_.isUndefined(options.is_enabled))
            return options.is_enabled(options.trigger);

        return options.trigger.is(':checked');
    };

    var show_fields = function(enable) {
        _.each(options.fields, function(field) {
            field.toggle(enable); 
        });

        if (!_.isUndefined(options.on_show)) {
            options.on_show();
        }
    };

    show_fields(is_enabled());
    options.trigger.change(function() {
       show_fields(is_enabled()); 
    });
};

seantis.formgroups.init = function() {
    
    this.add({
        trigger: $('#form-widgets-recurring-0'),
        fields: [
            $('#formfield-form-widgets-frequency'),
            $('#formfield-form-widgets-recurrence_end')
        ],
        on_show: function() {
            $('#form-widgets-frequency').change();
        }
    });

    this.add({
        trigger: $('#form-widgets-partly_available-0'),
        fields: [
            $('#formfield-form-widgets-raster')
        ]
    });

    // TODO make this generic
    this.add({
       trigger: $('#form-widgets-frequency'),
       fields: [
            $('#formfield-form-widgets-days')
       ],
       is_enabled: function(trigger) {
            if (! $('#form-widgets-recurring-0').is(':checked'))
                return false;
            return trigger.val() == 3; //rrule.DAILY
       }
    });
};

(function($) {
    $(document).ready(function() {
        seantis.formgroups.init();
    });
})( jQuery );