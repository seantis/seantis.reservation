if (!this.seantis) this.seantis = {};
if (!this.seantis.formgroups) this.seantis.formgroups = {};

seantis.formgroups.add = function(options) {
    var $ = jQuery;

    var is_enabled = function() {
        return options.trigger.is(':checked');
    };

    var show_fields = function(enable) {
        _.each(options.fields, function(field) {
            field.toggle(enable); 
        });
    };

    show_fields(is_enabled());
    options.trigger.click(function() {
       show_fields(is_enabled()); 
    });
};

seantis.formgroups.init = function() {
    
    this.add({
        trigger: $('#form-widgets-recurring-0'),
        fields: [
            $('#formfield-form-widgets-frequency'),
            $('#formfield-form-widgets-recurrence_end')
        ]
    });

    this.add({
        trigger: $('#form-widgets-partly_available-0'),
        fields: [
            $('#formfield-form-widgets-raster')
        ]
    });
};

(function($) {
    $(document).ready(function() {
        seantis.formgroups.init();
    });
})( jQuery );