if (!this.seantis) this.seantis = {};
if (!this.seantis.recurrence) this.seantis.recurrence = {};

seantis.recurrence.init = function() {
    $ = jQuery;

    var recurring = $('#form-widgets-recurring-0');
    var frequency = $('#form-widgets-frequency');
    var frequency_label = $('#form-widgets-frequency > label');
    var end_day = $('#form-widgets-recurrence_end-day');
    var end_month = $('#form-widgets-recurrence_end-month');
    var end_year = $('#form-widgets-recurrence_end-year');
    var end_label = $('#formfield-form-widgets-recurrence_end > label');

    var fields = [frequency, frequency_label, end_day, end_month, end_year, end_label];

    var is_enabled = function() {
        return recurring.is(':checked');
    }

    var enable_recurrence = function(enable) {
        _.each(fields, function(field) {
            field.attr('disabled', !enable);
        });
    };

    enable_recurrence(is_enabled());
    recurring.click(function() {
        enable_recurrence(is_enabled()); 
    });  
};

(function($) {
    $(document).ready(function() {
        seantis.recurrence.init();
    });
})( jQuery );