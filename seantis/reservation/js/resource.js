if (!this.seantis) this.seantis = {};
if (!this.seantis.resource) this.seantis.resource = {};

seantis.resource.highlight_timespan_actions = function() {
    $('.timespan-actions a').hover(function(e) {
        var id = $(this).data('timespan-id');
        var dates = $('.timespan-dates[data-timespan-id="' + id + '"]');

        dates.toggleClass('highlight');
        $(this).toggleClass('highlight');
    });
};


(function($){
    $(document).ready(function() {
        seantis.resource.highlight_timespan_actions();
    });
})(jQuery);
