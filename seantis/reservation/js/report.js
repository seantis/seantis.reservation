(function($){
    $(document).ready(function() {
        var report = $('.monthly-report');

        if (!report.length > 0)
            return;

        report.find('.reservation').click(function() {
            var el = $(this);
            el.toggleClass('show-details');
        });

        var options = {
            config: {
                onClose: function() {
                    window.location.reload();
                }
            }
        };
        reservation_overlay_init(report.find('.reservation-urls a'), options);
    });
})(jQuery);