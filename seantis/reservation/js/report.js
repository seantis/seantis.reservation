(function($){
    $(document).ready(function() {
        var report = $('.monthly-report');

        if (!report.length > 0)
            return;
            
        var show_details = function(elements, show) {
            elements.toggleClass('show-details', show);  
        };

        // Toggle reservation details
        report.find('.reservation').click(function() {
            show_details($(this));
        });
        
        // Toggle all reservation details
        $('.controlbox input[name="details"]').change(function() {
            var show = $(this).val() == 'show';
            show_details(report.find('.reservation'), show);
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