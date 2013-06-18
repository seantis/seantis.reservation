(function($){
    $(document).ready(function() {
        var report = $('.monthly-report');

        if (report.length === 0) {
            return;
        }

        var show_details = function(elements, show) {
            elements.toggleClass('show-details', show);
        };

        var show_timetable = function(elements, show) {
            elements.toggleClass('hidden-timetable', !show);
        };

        var update_url = function(base) {
            // takes the give url and replaces the query parts which may
            // be changed by the filter block at the top of the report with
            // the chosen values, producing a new url which will lead to the
            // same report with the same filter settings
            var uri = URI(base);
            var static_params = ['year', 'month', 'uuid'];
            var dynamic_params = _.difference(
                _.keys(uri.query(true)), static_params
            );

            _.each(dynamic_params, function(key) {
                uri.removeQuery(key);
            });

            if ($('.controlbox input[name="details"]:checked').val() == 'show') {
                uri.addQuery('show_details', '1');
            }

            if ($('.controlbox input[name="timetable"]:checked').val() == 'hide') {
                uri.addQuery('hide_timetable', '1');
            }

            _.each(hidden_resources(), function(resource) {
                uri.addQuery('hide_resource', resource);
            });

            _.each(hidden_statuses(), function(status) {
                uri.addQuery('hide_status', status);
            });

            return uri.normalize().toString();
        };

        var checkbox_values = function(selector, status) {
            var values = _.map($(selector), function(checkbox) {
                if ($(checkbox).is(status))
                    return $(checkbox).val();
            });
            return _.filter(values, function(value) { return ! _.isUndefined(value); });
        };

        var visible_resources = function() {
            return checkbox_values('.controlbox .resource-checkbox', ':checked');
        };

        var hidden_resources = function() {
            return checkbox_values('.controlbox .resource-checkbox', ':not(:checked)');
        };

        var visible_statuses = function() {
            return checkbox_values('.controlbox .status-checkbox', ':checked');
        };

        var hidden_statuses = function() {
            return checkbox_values('.controlbox .status-checkbox', ':not(:checked)');
        };

        var update_resource_status = function(changed) {
            var statuses = visible_statuses();
            var resources = visible_resources();

            // shortcut to hide all
            if (statuses.length === 0 || resources.length === 0) {
                report.find('div.day').hide();
                return;
            } else {
                report.find('div.day').show();
            }

            // get the selectors for the visible statuses and resources
            var status_selector = "";
            _.each(statuses, function(status) {
                status_selector += '.reservation-type.' + status + ', ';
            });

            var resource_selector = "";
            _.each(resources, function(resource) {
                resource_selector += '.resource[data-uuid="' + resource + '"], ';
            });

            // hide all elements of the changed selection
            if (changed == 'status')
                report.find('.reservation-type').hide();
            else
                report.find('.resource').hide();

            // show all visible
            $(status_selector).show();
            $(resource_selector).show();

            // go through visible resources and hide the ones that don't have
            // visible statuses
            _.each(resources, function(resource) {
                _.each($('.resource[data-uuid="' + resource + '"]'), function(resource_el) {
                    if ($(resource_el).find(status_selector).length === 0) {
                        $(resource_el).hide();
                        console.log('hit');
                    }
                });
            });

            // go through the days and hide the ones without visible resources
            _.each(report.find('div.day'), function(day) {
                var day_resources = $(day).find(resource_selector);
                if (day_resources.length === 0) {
                    $(day).hide();
                } else {
                    if (_.all(day_resources, function(resource) {
                        return $(resource).css('display') == 'none';
                    })) {
                        $(day).hide();
                    }
                }
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

        // Toggle all timetables
        $('.controlbox input[name="timetable"]').change(function() {
            var show = $(this).val() == 'show';
            show_timetable(report.find('.timetable-wrapper'), show);
        });

        // Toggle specific resources
        $('.controlbox .resource-checkbox').change(function() {
            update_resource_status('resource');
        });

        // Toggle statuses
        $('.controlbox .status-checkbox').change(function() {
            update_resource_status('status');
        });

        // Any changes to the controlbox -> new urls for prev/next
        $('.controlbox').change(function() {
            var box = $(this);
            var links = ['.next-month', '.previous-month'];

            _.each(links, function(link) {
                var a = box.find(link);
                a.attr('href', update_url(a.attr('href')));
            });
        });

        update_resource_status('resource');
        update_resource_status('status');

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