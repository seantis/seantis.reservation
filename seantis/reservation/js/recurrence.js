if (!this.seantis) this.seantis = {};
if (!this.seantis.recurrence) this.seantis.recurrence = {};

seantis.recurrence.init = function() {
    var $ = jQuery;

    var recurring = $('#form-widgets-recurring-0');
    var frequency = $('#formfield-form-widgets-frequency');
    var end = $('#formfield-form-widgets-recurrence_end');

    var fields = [frequency, end];

    var is_enabled = function() {
        return recurring.is(':checked');
    }

    var show_recurrence = function(enable) {
        _.each(fields, function(field) {
            field.toggle(enable);
        });
    };

    show_recurrence(is_enabled());
    recurring.click(function() {
        show_recurrence(is_enabled()); 
    });
};

(function($) {
    $(document).ready(function() {
        seantis.recurrence.init();
    });
})( jQuery );