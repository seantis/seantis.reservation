(function($){
    $(document).ready(function() {
        var report = $('.monthly-report');

        if (!report.length > 0)
            return;
            
        var show_details = function(elements, show) {
            elements.toggleClass('show-details', show);  
        };
        
        var show_resource = function(uuid, show) {
            var resources = report.find('.resource[data-uuid="' + uuid + '"]');
            resources.toggle(show);

            _.each(resources, function(resource) {
                var day = $(resource).parent();
                var show_day;

                if (day.is(':visible')) {
                    // if the day is visible we have a shortcut to figure out
                    // if any resources below the day are visible..
                    show_day = day.find('.resource:visible').length > 0;
                } else {
                    // ..which doesn't work if the day itself is invisible,
                    // as the children will be considered invisible in any case
                    show_day = _.any(day.find('.resource'), function(child) {
                        return $(child).css('display') != 'none';
                    });
                }
                    

                day.toggle(show_day);
            });
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
        
        // Toggle specific resources
        $('.controlbox .resource-checkbox').change(function() {
            var uuid = $(this).val();
            var show = $(this).is(':checked');
            
            show_resource(uuid, show);
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