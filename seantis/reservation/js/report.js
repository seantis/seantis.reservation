(function($){
    $(document).ready(function() {
        var report = $('.monthly-report');

        if (!report.length > 0)
            return;

        // Toggle reservation details
        report.find('.reservation').click(function() {
            var el = $(this);
            el.toggleClass('show-details');
        });

        // Hookup approve/decline overlays
        var force_reload = false;
        var options = {
            config: {
                onClose: function() {
                    if (force_reload)
                        window.location.reload();
                },
                onLoad: function() {
                    var form = this.getOverlay().find('form');
            
                    form.find('#form-buttons-approve, #form-buttons-delete, #form-buttons-deny').click(function() {
                        force_reload = true;
                    });
                }
            }
        };
        reservation_overlay_init(report.find('.reservation-urls a'), options);
    });
})(jQuery);