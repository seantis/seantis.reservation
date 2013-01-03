if (!this.seantis) this.seantis = {};
if (!this.seantis.my_reservations) this.seantis.my_reservations = {};

this.seantis.my_reservations.init = function() {
    reservation_overlay_init($('.my_reservations_link'), {});
};

this.seantis.my_reservations.update = function() {
    var container = $('.my-reservations-container');
    if (container.length === 0) {
        return;
    }

    /* this is wicked, the current page is reloaded, the fragment we are concerned
    about is extracted and drawn into the current page */
    var url = window.location;
    
    $('.my-reservations-container').load(url + ' .my-reservations', function() {
        seantis.my_reservations.init();
    });
};

(function($) {
    $(document).ready(function() {
        seantis.my_reservations.init();   
    });
})(jQuery);