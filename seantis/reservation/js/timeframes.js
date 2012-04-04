(function($) {
    $(document).ready(function() {
        var formselector = '#content-core form';
        var options = {
            formselector: formselector,
            closeselector: '[name=form.button.Cancel]',
            noform: 'reload',

            config: {
                onBeforeLoad: function(e) {
                    // If the formselector can't be found the overlay is
                    // immediatly discarded and the page reloaded. This
                    // is a bit of a hack to enable workflow_state changes
                    // without showing a meaningless overlay.
                    var overlay = this.getOverlay();
                    if (overlay.find(formselector).length === 0) {
                        window.location.reload();
                        e.preventDefault();
                    }
                }
            }
        };

        reservation_overlay_init($('#timeframes').find('a'), options);
    });
})(jQuery);