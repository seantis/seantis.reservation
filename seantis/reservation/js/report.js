(function($){
    $(document).ready(function() {
        if (!$('.monthly-report').length > 0)
            return;

        $('.monthly-report .reservation').click(function() {
            var el = $(this);
            el.toggleClass('show-details');
        });

    });
})(jQuery);