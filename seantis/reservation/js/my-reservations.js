if (!this.seantis) this.seantis = {};
if (!this.seantis.my_reservations) this.seantis.my_reservations = {};

this.seantis.my_reservations.init = function() {
    var options = {
        config: {
            onClose: function() {
                window.location.reload();
            }
        }
    };
    reservation_overlay_init($('.my_reservations_link'), options);
};

(function($) {
    $(document).ready(function() {
        seantis.my_reservations.init();   
    });
})(jQuery);