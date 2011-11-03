(function($) {
    $(document).ready(function() {
        var formselector = '#content-core form';
        
        $('a', $('#timeframes')).prepOverlay({
            subtype: 'ajax',
            filter: common_content_filter,
            formselector: formselector,
            noform: 'reload',
            closeselector: '[name=form.button.Cancel]',
            config: {
                onBeforeLoad: function() {
                    // If the formselector can't be found the overlay is
                    // immediatly discarded and the page reloaded. This
                    // is a bit of a hack to enable workflow_state changes
                    // without showing a meaningless overlay.
                    var overlay = this.getOverlay();
                    if (overlay.find(formselector).length === 0)
                        window.location.reload();
                }
            }
        });
    });
})(jQuery);