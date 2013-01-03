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

this.seantis.my_reservations.update = function() {
    var container = $('.my-reservations-container');
    if (container.length === 0) {
        return;
    }

    var url = window.location + '/my-reservations';
    
    $('.my-reservations-container').load(url + ' .my-reservations', function() {
        $(this).find('h1').replaceWith(function() {
            return '<h2>' + $(this).text() + '</h2>';
        });
    });
};

(function($) {
    $(document).ready(function() {
        seantis.my_reservations.init();   
    });
})(jQuery);