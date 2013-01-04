if (!this.seantis) this.seantis = {};
if (!this.seantis.your_reservations) this.seantis.your_reservations = {};

this.seantis.your_reservations.init = function() {
    reservation_overlay_init($('.your_reservations_link'), {});
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
        seantis.your_reservations.init();   
    });
})(jQuery);