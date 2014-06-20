if (!this.seantis) this.seantis = {};
if (!this.seantis.your_reservations) this.seantis.your_reservations = {};

this.seantis.your_reservations.init = function() {
    reservation_overlay_init($('.your_reservations_link'), {});

    $(".your-reservations .remove-url").click(function(e) {
        $(".your-reservations").load($(this).attr('href') + ' .your-reservations', function() {
            if ($(this).children().length === 0) {
                $(".your-reservations").remove();
            } else {
                $(this).replaceWith($(this).children());
            }
            seantis.your_reservations.init();

            $(document).trigger('reservations-changed');
        });

        e.preventDefault();
    });
};

this.seantis.your_reservations.update = function() {
    var container = $('.your-reservations-container');
    if (container.length === 0) {
        return;
    }

    /* this is wicked, the current page is reloaded, the fragment we are concerned
    about is extracted and drawn into the current page */
    var url = window.location;

    $('.your-reservations-container').load(url + ' .your-reservations', function() {
        seantis.your_reservations.init();
    });
};

(function($) {
    $(document).ready(function() {
        _.defer(seantis.your_reservations.init);
    });
})(jQuery);